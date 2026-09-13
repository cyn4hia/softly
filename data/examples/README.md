# examples

reference clips + sounds that live *in* the repo, for learning purposes.
everything here should be shareable (synthetic, original, or licensed) —
your own content belongs in your private folder configured via
`config/settings.yaml`, which softly only ever reads.

add files by dragging them onto the library's examples/sounds tabs (or the
inspo section of a new creation) in the GUI — or just copy them into this
folder by hand; both end up in the same place.

the bundled clips are procedurally generated through softly's own render
pipeline; rebuild them anytime with:

```bash
uv run python scripts/make_examples.py
```
