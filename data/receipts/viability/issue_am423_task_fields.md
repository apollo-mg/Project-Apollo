**Title:** `task.max_tokens` and `task.sampling` are parsed but never applied (+ one unsatisfiable task)

---

Ran HermesBench against several local models on `10bf4c6` and hit a failure mode that turned out to be three separate things in the harness rather than the models. All reproducible from the public repo.

## 1. `task.max_tokens` is parsed and never applied

Every task declares a budget:

```yaml
max_tokens: 4096
```

`TaskSpec.from_yaml` parses it (`types.py:106,136`). Nothing reads it back:

```
$ grep -rn 'task\.max_tokens\|task\.sampling' hermesbench/
(no output)
```

`run_real.py` reads only `task.allowed_tools`, `task.difficulty`, `task.id`, `task.max_turns`, `task.name`, `task.prompt`, `task.timeout_seconds`. `max_turns` is enforced; the token budget isn't.

**Effect:** generation is unbounded, so a task that doesn't converge runs until the wall-clock timeout and is scored `INFRA_ERROR`. Observed generation lengths on tasks declaring 4096: **8332, 8334, 8393, 8518, 8640** (one model) and **9178, 9379, 8850** (another). Each is ≈ timeout × decode rate — cut off by the clock, never by a budget.

This matters more than it sounds, because `INFRA_ERROR` leaves the denominator. One run scored `valid_pass_rate = 6/6 = 1.000` for a model that could not complete a single non-trivial task — every failure was classified as infrastructure.

## 2. `task.sampling` is parsed and never applied

```yaml
sampling: {temperature: 0.0, top_p: 1.0, top_k: -1, seed: 42}
```

Also parsed (`types.py:110,140`), also never referenced. Since the runner sends no sampling parameters, the **server's** defaults win.

**Effect:** the corpus specifies deterministic sampling for reproducibility and doesn't get it. We saw the same task pass in one run and run away in another on the same model and build — consistent with the declared seed never being applied.

## 3. `tasks/t02_file_read/t05_read_nested` is unsatisfiable as written

```yaml
name: "Read a deeply-nested path"
prompt: Read `add.py` (note the path is in a subdirectory).
fixture: {source: small_repo, globs: ["**/*"]}
```

The materialised worktree contains nine files, **all in the root, no subdirectories anywhere** — `add.py` included. The prompt asserts a path structure the fixture never creates.

Its verifier checks only that `read_file` was called at all:

```python
used = any(tc.function.name == "read_file" for msg in trace if role == "assistant" ...)
return PASS if used else FAIL
```

So a model that **ignores** the hint and reads `add.py` passes immediately, while one that takes the prompt at face value searches for a nonexistent subdirectory. Combined with (1) that search has no stopping point.

Minor, same family: `t02_read_tail` asks for *"the last 20 lines"* of a **10-line** file. `t01_read_head` asks for the first 50 of the same file and passes, so over-asking isn't fatal on its own.

## Why these compound

`t02_file_read` contains a deliberate false-premise task (`t04_read_missing` — read a nonexistent file, handle it gracefully) and an accidental one (`t05`). Establishing that something is *absent* requires exhausting a search, which has no natural stopping point — and with no token budget enforced, nothing stops it.

## Suggested fixes

1. Pass `task.max_tokens` through to the model request in `run_real.py` — the corpus already declares sensible budgets.
2. Either apply `task.sampling` or drop it from `TaskSpec` so it doesn't imply a guarantee that isn't there.
3. Either add the subdirectory to the `small_repo` fixture or reword the `t05` prompt.

Related to #3 (*Enforce task allowed_tools in real-Hermes runs*) — same underlying shape: task fields declared in YAML that don't reach the execution path.

Happy to open a PR for any of these if useful.
