# softly

an adaptive motion-graphics agent in a cute local GUI. you give it a prompt, a
little inspo, and (optionally) a sound — **Claude Fable 5 writes the animation
code**, softly renders it into a video on your machine, you watch and react,
and your feedback flows straight back into the next take. every prompt, take,
and note accumulates as learning data — the seed of a personal reward model
that view/interaction statistics will later sharpen.

## quick start

needs [uv](https://docs.astral.sh/uv/) (python is handled for you):

```bash
uv run softly
```

then open <http://127.0.0.1:8765>.

- **real generation** needs Anthropic credentials in your environment —
  `ANTHROPIC_API_KEY` or a profile from `ant auth login`. without them, softly
  falls back to a mock provider that echoes your inspo clip, so the whole
  feedback loop still works.
- **your own videos**: copy `config/settings.example.yaml` to
  `config/settings.yaml` (gitignored) and set `videos_dir`. clips are only ever
  *read* from that folder — never moved, copied into the repo, or committed.

## the loop

```
prompt + inspo clips + sound
        │
        ▼
  Claude Fable 5 writes a numpy animation script   ← previous code + your feedback
        │
        ▼
  local renderer (subprocess → PyAV → mp4, sound muxed in)
        │                                   ▲
        ▼                                   │ render errors go back
  you watch, rate ♥, tag aspects, leave notes — then revise
        │
        ▼
  data/learning/ (tracked): prompts, code, feedback, events
```

## repo map

| path | what lives there |
|---|---|
| `softly/` | python backend — FastAPI app, media streaming, session store, learning log |
| `softly/providers/` | generation backends behind one interface (`claude`, `mock`) |
| `softly/render_cli.py` | the render contract: `draw_frame(t) → RGB array` → mp4 |
| `web/` | the GUI — vanilla JS + CSS, no build step |
| `config/` | `settings.example.yaml` (copy to gitignored `settings.yaml`) |
| `data/examples/` | shareable reference clips + sounds (tracked) |
| `data/learning/` | sessions, feedback, event log — the adaptive data (tracked) |
| `data/generated/` | rendered video outputs (gitignored) |
| `scripts/` | `make_examples.py` regenerates the bundled example clips |
| `docs/ARCHITECTURE.md` | how it fits together + where it's meant to bend |

## privacy model

- paths to your private folders live only in `config/settings.yaml`, which git
  ignores; the repo never learns where your videos are. your clips are only
  ever read in place — never moved or copied.
- generated videos are gitignored; only the *metadata* about them (prompts,
  animation code, feedback) is tracked as learning data. note: the *filenames*
  of private clips you pick as inspo do appear in that tracked metadata.
- when the claude provider generates, a few still frames of your chosen inspo
  clips are sent to the Anthropic API so the model can see the reference.
- api keys come from the environment, never from files in the repo — and the
  subprocess that runs generated animation code gets no credentials at all.

## a note on generated code

softly executes the animation scripts the model writes — in a separate
subprocess with a hard timeout, on your machine, for you. the scripts are
constrained by prompt to pure numpy math (no file/network access), but this is
a local trust model, not a sandbox. see `docs/ARCHITECTURE.md`.
