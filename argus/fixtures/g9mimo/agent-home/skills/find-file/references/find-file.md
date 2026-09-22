# find-file reference notes

## Command patterns

### Fast, targeted search (preferred)
Search explicit paths with bounded depth before touching the whole tree.

```sh
find /home/mark/Documents /home/mark/Downloads /home/mark/Desktop \
  -iname "receipts-july.pdf"
```

### Full-tree search with pruning
Prune heavy/cache directories so the walk doesn't hang.

```sh
find /home/mark -iname "receipts-july.pdf" \
  \( -path '*/.cache' -o -path '*/node_modules' -o -path '*/.gradle' \
     -o -path '*/.cargo' -o -path '*/.rustup' -o -path '*/.pub-cache' \
     -o -path '*/.hf-cli' -o -path '*/.local' -o -path '*/.config' \
     -o -path '*/.npm' -o -path '*/.wine' -o -path '*/.dart-tool' \
     -o -path '*/.dartServer' \) -prune -o -iname "receipts-july.pdf" -print
```

### Verify before acting
Confirm the path exists and inspect it before deleting/moving.

```sh
ls -la /home/mark/Documents/receipts-july.pdf
```

## Timing notes (observed)
- Blind `find /home/mark -iname "..."` timed out at 180s; later at 588s+ (7+ min).
- Home has very large dirs that stall a full walk: cargo registry, rustup, `.cache`, `node_modules`, `.gradle`, `.config`.
- `find /home/mark/Documents /home/mark/Downloads /home/mark/Pictures` over the likely spots returned in one shot (fast).

## Workarounds
- If a full walk is unavoidable, run it in the background and poll:
  - `terminal(background=true, notify_on_complete=true)` so it survives the turn.
  - Or `process(action='wait'/'poll')` within the session.
- The security scanner (Tirith) blocks shell `for d in ...; do find ...; done` loops that build directory lists dynamically. Pass explicit paths instead of a glob-expanded loop.
- The `search_files` tool (target='files') is the native file-finder; use it instead of hand-typing `find` for quick checks.
