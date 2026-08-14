# Sanitized probe prompts — paste-only, contamination-resistant

Same five tasks as `PROBE_2026-08-13.md`, with every repo-identifying string renamed.
Reasoning required is unchanged; the numbers are the real measured ones.

**Why this exists:** a first run of T1 in a subfolder of this repo ended with the model
grepping for the symbol, reading `RESULT_HIP_VULKAN.md`, and then reading the probe file
itself — answer key and wrong-answer watchlist included. Result void. And since these
receipts are pushed to a public GitHub repo, a web-search-capable model can reach the same
answers without local access.

**Run protocol:**
1. `mkdir -p /tmp/probe-empty && cd /tmp/probe-empty` — barren cwd, nothing to walk up into.
   (Do **not** use a directory under `~` — `~/moe-cache-test/src` contains the real
   llama.cpp tree with T1's actual source.)
2. Launch the CLI there. Paste **one task per fresh session**.
3. Fixed wrapper, identical every run:
   `Answer from the information given. If you need evidence you don't have, say what you'd check.`
4. Hold the effort/thinking setting constant across models and record it.

Renamed identifiers below have no hits in this repo or on the public internet, so a grep
or a web search returns nothing and the model must reason from the prompt.

---

## S1 (was T1)

> A GPU backend called Spire has an optional weight-cache feature. `spire-weight-cache.cpp`
> exists and compiles. `nm -D` on the built `libspire.so` shows `spire_weight_cache_register`
> as an exported `T` symbol, and the cache compute shaders are present in the binary.
> The runtime nevertheless reports `weight cache disabled (no provider registered)`.
> Registration is called here:
> ```c
> backend_reg_t spire_backend_reg() {
>     static backend_reg reg = {...};
>     try {
>         spire_instance_init();
> #ifdef SPIRE_USE_BACKEND
>         spire_weight_cache_register(&reg);
> #endif
>         return &reg;
> ```
> The build was configured with `-DSPIRE_BACKEND=ON`. Why is the provider not registered?

## S2 (was T2)

> A GPU weight cache reports `cache disabled (no eligible weight tensors found)` on a card
> with compute capability 6.0. The tensors in question are all of a type the provider
> supports (23 types total). The device-capability gate has already been lowered to 600 and
> passes. Loading the *same file* on a different card engages the cache normally.
> Relevant constants:
> ```c
> cache_tensor_bytes_tier_hi_min = 512u << 10;   // used when capability >= 800
> cache_tensor_bytes_tier_lo_min = 1u << 20;     // used when capability <  800
> ```
> Each tensor is 8192 x 512 and its type packs 256 weights into 210 bytes.
> Why does this card report no eligible tensors?

## S3 (was T3)

> A tester claims: "On backend A the feature's output is byte-identical to feature-off,
> while on backend B it diverges. Therefore backend B's implementation has a bug."
> Both arms were verified individually deterministic. The one known confound was pinned
> off on both sides. Output streams were compared directly, feature-on vs feature-off.
> What is wrong with this reasoning?

## S4 (was T4)

> A tool files model files into directories named from their contents, e.g.
> `arch/512unit/comp-TypeA+TypeB-840KiB/`. Large models are split as
> `model-00001-of-00003.bin` … `-00003-of-00003.bin`.
> Observed: the three parts of one model land in three *different* directories, and part 1
> lands in a directory named `uniform`.
> Two distinct causes are in play. Name both.

## S5 (was T5)

> A binary model file is named `Foo-35B-TQ3_4S.bin`. A second is `Bar-75B-UD-IQ4-XL.bin`.
> A third is `Baz-UD-Q8_K_XL.bin`. Each contains hundreds of separate weight tensors, and
> the filename carries a single quantization label.
> What quantization do the *sub-expert* tensors in each actually use, and how would you
> determine it without downloading the entire multi-gigabyte file?

---

## Grading notes

S1–S2, S4–S5 grade exactly as their originals in `PROBE_2026-08-13.md`.

S5 changes character slightly and is *better* sanitized than in the original: with the
model names neutralized, the only honest answer is **"you cannot know from the label —
here is how to measure it."** A model that confidently expands `TQ3_4S` into a ternary
claim has failed the task on the prompt's own terms, with no lookup available to rescue it.

S2 keeps the real arithmetic: `8192 x 512` at `256 weights / 210 bytes` is
`(8192/256) * 210 * 512 = 860,160` bytes = **840 KiB**, under the 1024 KiB low-tier floor.
The stated answer must include that number, or it is a guess that landed nearby.
