# buun's qwen4 support vs the Tom/Mark/jabba DS4 direction — different axes, no overlap

**2026-09-02.** Read of `spiritbuun/buun-llama-cpp` master at `7a918624b`, fetched today.
`.194` powered down and `.73` asleep, so this is source comparison only — nothing built or run.

## Headline

**buun did not build the direction #324 is heading, and did not need to.** The two efforts are
orthogonal:

| | Tom / Mark / jabba (#324) | buun (master) |
|---|---|---|
| axis | **multi-GPU `-sm tensor`** via the meta backend | **single-GPU throughput** |
| hardware | 4x P100, 5090, M5 Max | 1x 3090, 64 GB |
| content | split states, DS4 patterns, memset, policy stop | MTP, VBR, MoE cache, long-context |
| DS4 | the whole point | untouched |

## The base arch came from neither of them

`6c84c7d5d model: add Qwen3.8-Flash-Next (qwen4exp) (#27742)` is an **upstream ggml-org commit**,
pulled into buun's tree via `dbcde9724` (integration sync, 2026-08-29). Upstream also shipped
`6fe749801 model: qwen4exp: reduce number of graph splits (#27880)`.

So "qwen4 support" in buun's announcement is upstream's arch plus his own optimisation layer on
top — not an independent implementation, and not a competitor to #324.

## Direct check against the three things we landed in Tom's tree

| our finding | Tom `85eb0596a` (+ my patch) | buun master |
|---|---|---|
| `GGML_OP_LIGHTNING_INDEXER` dispatch | added (my two-line patch) | **ABSENT** — identical gap |
| `memset_tensor` on the Meta buffer | implemented by Tom | **`nullptr, // TODO implement`** (line 1517) |
| AXIS_2 x AXIS_2 mul_mat rule | present | **present** |
| deepseek4 split patterns | present (`attn_q_a`/`attn_kv` MIRRORED, grouped `attn_output_a`) | **zero occurrences** |

buun's `llama_meta_device_get_split_state` carries patterns for standard attention, SSM/Mamba,
DFlash GDN tape and FFN — **nothing DS4-shaped**. If anyone pointed his master at DS4 under
`-sm tensor` today it would abort at the same `:1035 LIGHTNING_INDEXER` stop I hit on 2026-08-30,
and then at the memset stop behind it.

## Correction to my own record: the AXIS_2 rule was upstream's, not mine

`git log -L` on those lines in buun's tree dates them to
`c7cf9f46c merge: sync with upstream/master (479 commits) — 2026-07-06`.

The rule existed **upstream since at least 6 July**. Tom said as much when he took it
(*"matches the upstream DS4 implementation, including the split_states_equal guard"*), so nothing
was misrepresented to him — but `RESULT_85eb0596a_DS4.md` describes it as *"the rule I proposed"*,
which reads as novelty. It was independent re-derivation of existing upstream code. Turboquant
lacked it only because that fork had diverged from upstream before the rule landed.

**The LIGHTNING_INDEXER dispatch is a different matter** — absent from upstream-synced buun master
*and* from Tom's tree, so that one is genuinely ours.

## What buun actually built (≈10k insertions across the qwen4 series)

| commit | content |
|---|---|
| `97474a38b` | qwen4: optimized inference, MTP, VBR — 9,948 insertions / 90 files |
| `295850adc` | restore Turbo V output in sparse attention |
| `fd56dfcdd` | harden adaptive caching + long-context paths |
| `6a2eb3232` | fix recurrent PLE speculative resize |
| `0f6a7267a` | unrotate Turbo K after QSA gather |
| `2d5ef7910` | **support official shared MTP sidecars** |
| `283ba19ed` | vbr: configurable dynamic entry tiers |
| `65eb44ebc` | hip: RDNA2 FA occupancy + batch VBR VMM maps |

His reported numbers (Discord, 2026-08-30/09-02): **53 tok/s** on 1x3090 with the model fully in
RAM, **41–41.6 tok/s** at 64 GB with n-gram on SSD, UD-Q4_K_XL + MTP. Single GPU throughout —
consistent with a tree that has no DS4 tensor-split work in it.

## Two items that touch our stack

1. **`2d5ef7910` — "official shared MTP sidecars."** We concluded on 2026-08-29 that Qwen 3.8
   ships MTP *inside* the main GGUF (`qwen35.nextn_predict_layers = 1`, `blk.64.nextn.*`), which is
   why `.73` runs `--spec-type draft-mtp` with no draft model. A separate sidecar path suggests
   some providers ship MTP as its own file. Worth knowing before changing `.73`'s `WP_START_CMD`;
   nothing to change today.
2. **`283ba19ed` — configurable dynamic VBR entry tiers.** Directly relevant to the VBR article,
   and it postdates every VBR measurement in `data/receipts/vbr-fidelity/`. Any republished VBR
   number should name the commit it was taken at.

## Not claimed

No build, no benchmark, no verification of buun's throughput figures. Source reading only, on a
tree fetched today. `.194` is powered off and `.73` was left asleep deliberately.
