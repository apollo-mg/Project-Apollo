# Why VBR is uniquely hard to benchmark — and the one trap anyone measuring it will hit

**2026-08-18.** Design note, not a measurement. Everything below is read from buun
`02f8581` source (`src/llama-kv-cache.cpp`, `common/arg.cpp`), with line references, so it
can be checked. Defines `BACKLOG U7` properly.

Prompted by Mark: *"buun is fairly convinced his VBR codec is the best 'in practice', since
it only degrades when necessary… it's just the most annoying way to test I can think of. I
would likely run it just based on the premise, and I think a lot of people will."*

## CORRECTED — `-ctk vbr` **does** turn VBR on. My original claim here was wrong.

> **This section originally claimed that `-ctk vbr` only sets the type and that the dynamic
> controller needs `VBR_VMM=1`. That is false, and the error was mine: I read
> `llama-kv-cache.cpp` from line 1033 and missed line 1031.**
>
> ```c
> bool vbr_dynamic_wanted = vbr_params_.dynamic;   // <- line 1031, threaded from the CLI
> if (const char * e = getenv("VBR_VMM"))      { vbr_dynamic_wanted = atoi(e) != 0; }
> else if (const char * m = getenv("VBR_MODE")) { vbr_dynamic_wanted = strcmp(m,"dynamic")==0; }
> ```
> The comment above it is explicit: *"Driven by `cparams.vbr_dynamic` (threaded through
> `create_memory`); `VBR_VMM` / `VBR_MODE` env remain **developer overrides in BOTH
> directions**."* The env vars override the flag; they are not required by it.
>
> `docs/vbr.md` says the same in the first line of its quickstart — `llama-server -m model.gguf
> -ctk vbr`, *"That single flag is the complete product."* And `common/arg.cpp:905-930` does
> real work to make it one flag: it implies vbr on the opposite side when that side was unset
> (pinning it if explicitly set), force-enables `--kv-unified` under `-np > 1` because
> per-sequence streams would silently disarm the controller, and warns when developer env is
> present. **This is careful one-flag design, and I mis-described it.**
>
> `AFM-17` again — behaviour inferred from a source fragment. The fragment was real; the
> conclusion drawn from it was not. Left visible rather than silently rewritten.

## What is actually true: `frontier-hazard` cannot reach VBR at all

The `dynamic=0 … -> wanted=0` gate line we observed is real, but its cause is the **benchmark
tool**, not the flag.

`frontier-hazard` **bypasses `common/arg.cpp` entirely** — it has a private option parser and
a private `type_from_str` that walks `ggml_type_name()` (`frontier-hazard.cpp:46-54`). So:

- `-ctk vbr` is rejected outright (`error: unsupported KV cache type 'vbr'`) because `"vbr"`
  is an **alias resolved in `arg.cpp:342`**, and `ggml_type_name()` never returns aliases;
- `cparams.vbr_dynamic` is never set, so even naming `turbo3_tcq` directly gives the static
  tier with the controller disarmed.

**So buun's own quality-bench tool cannot measure buun's own default KV mode.** That is the
observation worth sending him, and it is a much smaller, more accurate claim than the one this
note originally made. `RESULT_U5B_BUUN.md`'s `turbo3_tcq` row remains valid and correctly
labelled as **VBR's static entry tier**, measured through that limitation.

## Why the premise is better-founded than "it degrades when needed"

`llama-kv-cache.cpp:1473-1481`:

> *demand-driven sheds may only spend the leading f16→t8 band of the price order — the one
> cheap **AND domain-reversible** rung (**sub-t8 sheds imprint irreversible re-encode error
> into existing tokens**). A custom `VBR_DEGRADE_ORDER` carries no band guarantee, so it
> disables demand shedding.*

Two things follow, and they are the substance of Mark's *"as long as you're smart about WHAT
you allow to degrade"*:

- **The default shed is capped at the reversible rung.** Dropping below turbo8 needs explicit
  typed consent (`vbr_floor_typed_ = vbr_params_.min_bits_explicit`, `:1487`), and the raw
  `VBR_MIN_BITS` debug env deliberately **does not** grant it. That is a designed refusal to
  quietly cause irreversible loss.
- **Degradation rewrites tokens already in the cache.** This is the property no static codec
  has, and it is what makes benchmarking hard.

## The actual difficulty: VBR's error is path-dependent

A static codec's error is a function of its **configuration**. VBR's error is a function of
its **history** — which layers shed, at what point in the sequence, and how many times
existing tokens were re-encoded on the way there.

**Two runs that finish at identical bits/value can have different fidelity**, depending on
when the pressure arrived. No single-shot benchmark can distinguish them, because the thing
being measured is not a state but a trajectory.

Worse for reproducibility: the budget is derived from **live per-device free memory**
(`:1497-1519`, `VBR_BUDGET_MIB` overrides it and is documented as *"forced-budget
instrumentation must never grow"*). Absent that override, **VBR's behaviour depends on what
else is resident on the GPU.** Co-tenancy is a first-class concept in this code.

### Our instrument is structurally blind to all of it

`frontier-hazard` builds one context, prefills once, scores, exits. There is no progressive
pressure and no re-encode event, so **the entire mechanism VBR exists for never occurs.** And
at `--n-prefix 128` the cache is 1–4 MiB against a budget in GiB, so the trigger cannot arm
even with the env set. Combined with `SCOPE_CORRECTION_136_TOKENS.md`: **VBR is not
under-measured by our panels, it is unmeasurable by them.**

## Mark's multi-turn question and the VBR question are the same experiment

He asked earlier: *"how often does using a lower fidelity bitrate actually change the overall
outcome of a multi-turn exchange."* That is exactly the VBR test. A long multi-turn session is
what generates progressive memory pressure, fires the shed, and accumulates re-encode error —
**preferentially in the oldest tokens**, which is where the system prompt and task definition
live. A static codec damages all positions uniformly; VBR concentrates its irreversible damage
in the history. Whether that is better or worse **in practice** is precisely the open question,
and it is not answerable by any panel in this repo.

## What a fair test requires

1. **Equal footprint, not equal nominal bits.** Pin `VBR_BUDGET_MIB` to exactly the bytes a
   static codec occupies at the same context length (now computable exactly —
   `RESULT_U5E_KVSIZE.md` gives per-codec bits/value plus the fixed 128 KiB turbo overhead).
   VBR wins iff dynamic allocation beats uniform allocation **at the same cost**. Comparing an
   unbudgeted VBR against a static codec is the unequal-budget error this project already made
   once.
2. **The controller actually armed** — through `llama-server -ctk vbr` (which handles
   `--kv-unified` itself), with the `VBR degrade #…` steps under `-v` observed, not assumed.
   **Not through `frontier-hazard`, which cannot arm it.**
3. **Depth sufficient for the budget to bind.** No pressure, no VBR.
4. **Multi-turn, with an f16-vs-f16 control arm.** Baseline nondeterminism on this fleet is
   established (`agent-benchmark-determinism`: HA-04 went 35/100/100/35 at temp 0), so
   divergence-above-baseline is the only interpretable signal.

## A question worth putting to buun

buun has said he swept layer pricing and has *"a generic layer pricing schedule."* **At what
context depth was the sweep run?**

It matters because optimal allocation may invert with depth. `RESULT_U5CD_PLACEMENT.md` finds
V favoured over K for the turbo2/turbo3 pair **at 136 tokens**; h4rm0n1c's K-first intuition
comes from long-context use, and key-retrieval damage is exactly the failure that should
compound with history length. If the sign flips, a schedule swept shallow is **mispriced at
the depth people actually run**, and vice versa. That is a concrete, checkable question rather
than a benchmark result, and it is probably worth more to him than another static panel.
