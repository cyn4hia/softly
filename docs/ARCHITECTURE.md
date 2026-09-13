# softly — architecture

softly is deliberately small and loosely joined: the parts most likely to
change (how videos get generated, where learning signal comes from) sit behind
narrow seams, and everything else is boring on purpose.

## components

```
web/  (vanilla JS, hash router)          softly/  (FastAPI, one process)
┌──────────────────────────┐             ┌───────────────────────────────────┐
│ views: home · create ·   │   /api/…    │ routers: sessions · library ·     │
│ session · library ·      │ ──────────▶ │          learning_routes          │
│ learning                 │             │        │                          │
└──────────────────────────┘             │        ├─ store.py     JSON docs  │
                                         │        ├─ media.py     sources +  │
                                         │        │               range HTTP │
                                         │        ├─ learning.py  events +   │
                                         │        │               stats      │
                                         │        └─ providers/   generation │
                                         │             │ base.py  (contract) │
                                         │             ├ claude_code.py      │
                                         │             └ mock.py             │
                                         │        rendering.py → subprocess  │
                                         │        render_cli.py → PyAV mp4   │
                                         └───────────────────────────────────┘
```

## the generation seam (most likely to change)

`softly/providers/base.py` defines the whole contract:

- `GenerationRequest` — prompt, tags, inspo refs, sound ref, full feedback
  history, revision instructions, previous code, output dir.
- `GenerationResult` — ok, media ref, human note, the code behind the video, log.
- `GenerationProvider.generate(request) → result` (async).

routers know nothing beyond this. adding a new backend (hosted video model,
local ComfyUI, whatever) = one module in `providers/` + one registry line +
a `provider:` value in settings. if a provider can't run at all it raises
`ProviderUnavailable` and the session router falls back to `mock` with an
explanatory note instead of failing the creation.

### the claude provider

`claude_code.py` drives `claude-fable-5` (configurable):

1. builds one user message: sampled JPEG frames from each inspo clip
   (`frames.py`, via PyAV+Pillow), then the brief (prompt, tags, sound,
   and on revisions: previous code + all feedback + instructions).
2. streams the response (long generations; avoids HTTP timeouts). thinking is
   always on for fable — the request deliberately omits any `thinking` config
   and steers depth with `output_config.effort` from settings.
3. refusal fallback: when `fallback_model` is set, the API retries a declined
   request on that model server-side (`server-side-fallback-2026-06-01` beta).
4. extracts the python code block and hands it to the renderer. on a render
   failure the stderr goes back to the model (up to 2 repair round-trips) —
   the response `content` is passed back unchanged, as fable requires.

### the render contract

`render_cli.py` runs in a subprocess (`rendering.py`, hard timeout, killed on
overrun) so bad generated code can't wedge the app. a script must define
`WIDTH/HEIGHT/FPS/DURATION` and `draw_frame(t) → (H, W, 3) uint8 RGB`; the CLI
clamps dimensions/fps/duration, encodes h264/yuv420p via PyAV, and best-effort
muxes the chosen sound (AAC, trimmed to duration — failures degrade to a
silent video, never a failed take). `scripts/examples/*.py` are hand-written
scripts of the same contract; `make_examples.py` renders them into
`data/examples/` through the very same pipeline (dogfooding).

**trust model:** generated scripts are executed locally, unsandboxed beyond
subprocess + timeout. constraints (numpy-only, no I/O) are enforced by prompt,
not by a jail. acceptable for a personal tool; revisit before ever running
untrusted scripts.

## media sources

`media.py` maps symbolic sources to directories:

| source | directory | notes |
|---|---|---|
| `mine` | `library.videos_dir` from settings | private, outside repo, read-only |
| `sounds` | `library.sounds_dir` from settings | private, optional |
| `examples` | `data/examples/` | tracked, shareable |
| `generated` | `data/generated/` | gitignored outputs |

everything downstream passes `{source, path}` refs around; streaming goes
through one range-aware endpoint (`/api/media/{source}/{path}`) with
`is_relative_to` traversal protection. adding a source touches only
`source_roots()` (plus the listing whitelist per kind).

## data & learning

- **sessions** — one JSON doc per creation in `data/learning/sessions/`
  (title, prompt, tags, inspo/sound refs, versions with code + note + status +
  feedback). tracked in git: this *is* the adaptive dataset. written
  atomically (tmp + rename).
- **events** — append-only `data/learning/events.jsonl` (creation, generation,
  feedback, tagging, deletion). this is the raw log a reward model can train
  on later; it is never read back to reconstruct state.
- **stats** — always derived fresh from session docs (`learning.py`), so the
  two stores can't drift.
- **library tags** — `data/learning/library_tags.json`, genre labels for
  matching prompts to visuals.

### planned evolution (kept in mind, not built)

- **view/interaction statistics**: will arrive as per-video records joined to
  sessions — an importer + a `stats` section on the session doc, feeding the
  same events log. nothing needs restructuring for this.
- **reward model**: consumes `events.jsonl` + session docs + stats. that's why
  events carry full payloads rather than ids alone.
- **generation becomes slower/queued**: versions already have
  `rendering/ready/failed` states and the UI polls, so a real job queue can
  replace the in-process asyncio task without API changes.

## privacy invariants (do not break)

1. private folder paths exist only in gitignored `config/settings.yaml`.
2. files under `mine`/`sounds` are opened read-only for streaming and frame
   sampling; nothing ever writes into, copies out of, or moves files in those
   folders (the mock provider streams the inspo clip in place rather than
   copying it).
3. `data/generated/` stays gitignored (video binaries + generated scripts).
4. session docs store only `{source, relative path}` refs — never absolute
   paths, and render logs are scrubbed of the repo root before persisting.
   (relative filenames of private clips do appear in tracked learning data;
   keep that in mind if filenames themselves are sensitive.)
5. credentials come from the environment; nothing in the repo holds keys, and
   the render subprocess (which executes model-written code) receives a
   minimal environment with no credentials in it.
6. when the claude provider is active, sampled still frames of the chosen
   inspo clips — including private ones — are sent to the Anthropic API as
   part of the generation request. pick inspo accordingly.
7. the server only answers requests with a local Host header (DNS-rebinding
   defense) and binds 127.0.0.1 by default.
