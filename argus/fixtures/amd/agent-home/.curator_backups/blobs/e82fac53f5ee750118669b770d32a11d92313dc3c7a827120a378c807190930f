---
name: find-file
description: Locate a file on the local machine when find hangs.
tags: [terminal, filesystem, search]
---

# find-file

Locate a file or directory on the local machine.

## When to use
- User asks to find / locate a file, PDF, receipt, log, or any named artifact.
- A `find` command is hanging or timing out.

## Strategy
1. Search the most likely locations first with explicit paths (Documents, Downloads, the home root, a known folder). These are fast.
2. Bound depth with `-maxdepth` to avoid walking the whole tree.
3. For a full-tree search, prune heavy/cache directories first so the walk doesn't hang (see references).
4. If it is still slow, run the scan in the background and poll it rather than blocking the turn.
5. Verify the result before acting on it (stat / read the file back) — e.g. before deleting.

## Pitfalls
- A blind `find /home/mark -iname "..."` frequently times out. The home directory contains very large directories (cargo registry, rustup, .cache, node_modules, .gradle, .config) that stall a full walk. Use maxdepth, targeted paths, or pruning.
- Never claim "find doesn't work" — the tool works; the tree is just huge.
- The security scanner (Tirith) blocks shell `for d in ...; do find ...; done` loops that build directory lists dynamically. Pass explicit paths instead of a glob-expanded loop.
- A file may vanish between searches (deleted by the user, moved, or a race). If a re-check finds nothing, say so honestly rather than reporting stale data.

## References
- references/find-file.md — concrete command patterns, prune lists, and timing notes.
