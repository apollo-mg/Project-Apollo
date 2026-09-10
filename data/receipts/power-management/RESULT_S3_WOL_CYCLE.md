# .73 survives S3 suspend and wakes on a magic packet — with the P100s intact

**2026-08-27**, `.73` (`ai-p100-sli`, i7-8700K, 16 GB, 2× Tesla P100-PCIE-16GB, sm_60),
Kubuntu, kernel `7.0.0-29-generic`. No `llama-server` running; both GPUs 0 MiB at test start.

## Result

| stage | evidence |
|---|---|
| suspend entered | `kernel: PM: suspend entry (deep)` — **13:49:47** |
| suspend exited | `kernel: PM: suspend exit` — **13:50:03** |
| time actually suspended | **9.9 s** (`CLOCK_BOOTTIME − CLOCK_MONOTONIC`; monotonic excludes suspend) |
| woken by | Wake-on-LAN magic packet to `e0:d5:5e:b5:9e:b3`, UDP broadcast :9 |
| kernel accounting | `suspend_stats/success = 1`, `fail = 0` |
| GPUs after resume | both `Tesla P100-PCIE-16GB`, 0 MiB, 47/50 °C, **persistence mode still Enabled** |
| NVRM errors / Xids since resume | **0** |

**Both P100s survived a deep S3 cycle and came back without a driver reload.** The
`nvidia-suspend`/`nvidia-resume` services and `NVreg_PreserveVideoMemoryAllocations=1` were
already configured on this host — nothing was installed for this test.

## The trap this test was designed around

`NVreg_TemporaryFilePath=/var`, and `/var` has **24 GiB free** against **32 GiB** of VRAM across
two cards. Suspending with models resident would attempt a spill that does not fit. The test
therefore asserted `pgrep -xc llama-server == 0` as a **precondition** and aborts otherwise.

That is also the right operational rule: **unload before suspending.** Resume then costs a model
load rather than a 32 GiB disk round-trip, which is faster in both directions.

The Optane (`INTEL MEMPEK1W032GA`, 27 GiB usable, 17 GiB already a swapfile) does not change
this — even emptied it is smaller than the 32 GiB a full spill needs. It is correctly sized for
**hibernate** (swap >= RAM), not for VRAM preservation.

## Two-hour soak — PASSED (2026-08-27 14:01 → 16:02)

The 10-second cycle proved the mechanism; this tested whether it holds.

| measure | result |
|---|---|
| time asleep | **7,260 s (2 h 1 m)** |
| **spurious wakes** | **0** — polled every 60 s throughout |
| wake → ping | **10 s** |
| wake → SSH ready | **10 s** |
| suspended seconds (`BOOTTIME − MONOTONIC`) | **7,269.0** — independent confirmation |
| `suspend_stats` | `success = 2, fail = 0` |
| NVRM errors / Xids | **0** |
| GPU temps | **48/51 °C → 41/43 °C** |

Two things this settles. **The NIC holds its wake state across a multi-hour sleep** — the
failure mode a short test cannot see. And **wake-to-usable is 10 seconds**, not the 60–120 s
estimated; resume from S3 keeps RAM intact, so the only real cost is reloading the model.

The 7 °C drop on both cards is the thermal benefit stated directly: the machine is a
~100–120 W space heater when idle, and this is what turning it off looks like.

## End-to-end — a request to a powered-down machine returns a completion

**2026-08-27 16:55.** `.73` suspended, one OpenAI-format request sent to the wake proxy
(`modules/wake_proxy.py`), no manual intervention.

| stage | elapsed |
|---|---|
| magic packet -> node reachable | **10 s** |
| llama-server launch -> `/health` (21 GB Q6_K off NVMe) | **52 s** |
| **request -> completion, from powered down** | **77 s** |
| **warm second request** | **2.5 s** |

`HTTP 200`, real generated content, `usage: 32 completion tokens`. The 52 s load independently
reproduces the figure in the node's own llama-swap config ("NVMe, 51s loads").

Wake has now succeeded **4 for 4 at 10 s**: two isolated cycles, one after a 2-hour soak, one
under the proxy.

### Auto-suspend and the round trip

Idle-suspend had never run. With `WP_IDLE=120`:

```
16:57:50  proxy up (idle=120s, suspend on)
16:59:50  idle 120s >= 120s -- suspending
16:59:50  stopping llama-server before suspend (VRAM spill would not fit)
16:59:59  suspended
```

Then a second request to the machine that had **suspended itself**:

| | |
|---|---|
| wake -> reachable | **10 s** |
| launch -> `/health` | **51 s** |
| **request -> completion** | **99 s** |
| answer | `17 x 23` -> **391, correct** |

The full cycle is closed: **wake on demand -> serve -> idle -> unload -> self-suspend -> wake
again.** Wake is **5 for 5 at 10 s**.

Note the answer arrived in `reasoning_content` with `content` empty -- a reasoning model given
200 tokens spends them thinking. Same shape as the `max_tokens: 32` failure earlier in this
campaign; any checker reading only `content` scores this as a non-answer.

### The bug this test found, which reading could not

First attempt returned `HTTP 500 upstream command exited prematurely` in 18 s. The node already
ran **`llama-swap`** on port 8080 as its serving entry point. The proxy's launch bound-failed,
then llama-swap answered `/health` with 200 — so the proxy logged **`start: /health OK` in the
same second it launched a 21 GB model** and declared it ready.

> **`/health` proves something is listening on that port. It does not prove the model you asked
> for is loaded.** A readiness probe that any other service can satisfy is not a readiness probe.

Fixed two ways: a **managed mode** (empty start command) that waits for a node's own model
manager instead of fighting it for the port, and — for this node, where llama-swap was unwanted
— stopping and disabling llama-swap so the port is genuinely ours.

### Incidental finding: the node's serving stack was already dead

llama-swap advertised all four models and failed every request (`upstream command exited
prematurely`). Its config points at `/mnt/models/*.gguf`; the files had been reorganised into
`/mnt/models/AI_Models/` during an earlier consolidation. Pre-existing, unrelated to this work,
and unnoticed because the machine is usually off. Its own config also warned that idle traffic
can reload a model mid-benchmark — a live hazard for any A/B run on this box, now removed.

## Installed as a service (2026-08-27 19:00)

`~/.config/systemd/user/apollo-wake-proxy.service`, `enabled`, linger on. Serving
**Qwen3.8-27B-Q6_K** (streamed from `.194`, byte-count verified: 22,884,408,288).

| check | result |
|---|---|
| cold request **through the service**, node powered down | **79 s**, `HTTP 200`, answer `391` correct |
| wake -> reachable | **10 s** (7th consecutive) |
| launch -> `/health` | 49 s |
| model actually answering (`/props`) | `Qwen3.8-27B-Q6_K.gguf` |
| samplers as served (`/props`) | temp 1.0, **min_p 0.0**, top_p 0.95, top_k 20 |
| `kill -9` the service | restarted in <14 s, port rebound, node untouched |
| reboot survival | `enabled` + `linger=yes` + `default.target.wants` symlink present |

`min_p` is pinned **in the unit file**, not left to memory: llama.cpp defaults to 0.05 while the
card specifies 0.0, and that silent override contaminated earlier runs in this campaign. The
unit is now the durable record of the intended sampling.

`WP_IDLE=1800` — long enough that a working session never pays the 79 s cold start, short enough
that an idle night is not spent heating a room at ~110 W.

## What this does NOT establish

- Two cycles total (`success = 2`). An existence proof for a 2-hour sleep, not a reliability
  figure for weeks of them.
- Untested with models loaded (deliberately — see above), and with no client mid-request.
- One cycle. `success = 1` is an existence proof, not a reliability figure.
- `nmcli` reports wake-on-lan as `default`, not an explicit `magic`. It works today; it is not
  pinned against a NIC reset or a NetworkManager update.

## Method notes

Two harness bugs surfaced and are recorded because both produced *confident wrong output*:

1. `bc` is absent on the control plane, so every elapsed-time print rendered as `after s`. The
   cycle still ran; the timings were simply lost. Replaced with `awk`.
2. The first post-resume health check grepped `journalctl -b -n 200`, which truncates to the last
   200 lines **before** matching. It reported `PM suspend matches: 0` — i.e. "this never
   suspended" — for a cycle that demonstrably did. The unbounded query found the records
   immediately. **A negative result from a truncated search is not a negative result.**
