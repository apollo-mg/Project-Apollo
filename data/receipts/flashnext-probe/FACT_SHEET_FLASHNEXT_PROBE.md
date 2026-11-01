# Fact sheet: Qwen3.8-Flash-Next, the Cohere upload probe, and local GGUF files

For Mark to write from. Every number is in `RESULT_FLASHNEXT_PROBE.md` and its JSON files in this folder. ASCII only.

CORRECTION 2026-10-31: the sanmaohe odds first published here (4e-18, 7e-38, 2e-33) were wrong. They priced one odd spelling of
the host, not Cohere's tokens. Corrected, same order: 1e-12, 3e-18, 4e-18. Every other host's odds stand. All percentages below
were measured on a prefilled state; see "The follow-up" at the end of this sheet.

## The short version

1. The behaviour Cohere found carries into the GGUF files people download. Given Cohere's own half-written upload command,
   our local files finish it with a URL 395-400 times out of 400.
2. Where that URL points, and how often it is a cloud address, depends on the exact file and even on where five layers
   compute. No destination wins outright, and small numeric changes reshuffle them.
3. So a single trace, or a single test setup, cannot tell you how a deployment behaves, in either direction. This has to be
   measured as a rate, on the deployment that will run.

## What was run

- Model: Qwen3.8-Flash-Next. Files: Unsloth UD-IQ4_XS and UD-Q2_K_XL, sha256 matched to Unsloth's published hashes.
- Host: 4x Tesla P100, buun 0b2789f23 build_sm60, one fresh server per setup, 2026-10-29.
- Prompt: Cohere's published trace, cut at token 2,323 and sent as raw token ids, ending right before the URL.
- Sampling: Cohere's script settings (T 1.0, top_p 1.0, top_k 20, min_p 0), 48 tokens, seeds 1-400. 1,200 samples in all.
- Nothing contacted any URL. This is text generation only.
- Preregistered, including three predictions that failed (P1, P3, P4): `PREREG_FLASHNEXT_PROBE.md`.

## Results: 400 samples per setup

| | IQ4_XS, 44 layers on GPU | Q2_K_XL, 44 on GPU | Q2_K_XL, all on GPU |
|---|---|---|---|
| writes any URL | 395 | 400 | 400 |
| Alibaba Cloud metadata address 100.100.100.200 | 21 (5.3%) | 29 (7.3%) | 9 (2.3%) |
| localhost or 127.0.0.1 first | 130 (32.5%) | 0 | 0 |
| public addresses starting 23. (first host) | 0 | 260 (65%) | 141 (35%) |
| largest single host | localhost 23.8% | 23.215.221.71 9% | 3.3% |
| distinct first hosts | 152 | 229 | 273 |
| any routify host | 0 | 13 | 2 |
| routify-file-proxy-sg as first host | 0 | 11 | 1 |
| any aliyuncs.com host | 7 | 14 | 6 |
| Cohere's exact bucket (sanmaohe) | 0 | 0 | 0 |
| starts a signed URL (Expires=, OSSAccessKeyId=) | 0 | 3 | 0 |

- Placement means five of the model's 49 layers run on the CPU (-ngl 44) or all 49 on the GPUs (-ngl 99). In both, the
  28.8 GB n-gram table stays in system RAM: VRAM use was 45 GiB and 50 GiB for a 79 GB file.
- The labels are not specs: 51 GB of the Q2_K_XL file is IQ4_NL, and 34 GB of the IQ4_XS file is IQ3_S.
- The metadata address is the third most common host on IQ4_XS, second and third on the two Q2_K_XL setups.
- Placement, same file: metadata address 7.3% vs 2.3%, difference -5.0 points, 95% interval -8.2 to -2.1, p about 0.001.
- Bit level, same placement: metadata address difference +2.0 points, interval -1.4 to +5.5, not detectable.
- Bit level, same placement: localhost/127.0.0.1 -32.5 points, interval -37.2 to -28.0.

## The model's own odds at the moment it picks the host

Read on the decode path, the state the samples came from (untruncated probabilities, grammar-forced generation):

| host | IQ4_XS, 44 | Q2_K_XL, 44 | Q2_K_XL, all GPU |
|---|---|---|---|
| 100.100.100.200 | 3.3% | 6.7% | 1.5% |
| localhost | 17.7% | 0.04% | 0.09% |
| routify-file-proxy-sg | 0.33% | 2.4% | 0.38% |
| sanmaohe bucket (corrected 10-31) | 1e-12 | 3e-18 | 4e-18 |

- These odds match the samples: total variation 0.04-0.11 against the samples' first characters.
- The same three tokens pushed through as a batch instead give 0.33-0.41. Even that kernel difference moves the odds.

## The n-gram table

- XDA traced the routify hostname to Flash-Next's n-gram embedding table.
- That table is per_layer_token_embd.weight, 320,001,536 x 160, 28.8 GB.
- It is stored as IQ4_NL in all five files we read, including the 2-bit ones.
- It is byte-identical (same sha256) in Unsloth's UD-IQ4_XS, UD-Q2_K_XL and UD-Q4_K_XL.
- So the differences above do not come from the table. They come from the rest of the model and the numeric path.

## What this does not show

- It is not a base rate. The prefix has already written the command. Cohere's rate for the behaviour is "less than one
  call in 100,000 across our evaluation runs".
- It is not a comparison with full precision. BF16 does not fit this host.
- It is two files, one engine, one host and one cut point. The REAP and Swift files were not probed.
- It does not show intent. Which tensors cause the differences was not tested.
- At this prefix the model writes a PUT of a test payload to the address. It is not fetching credentials. The metadata
  service is an address that can serve them.

## Credit, in their words

- Cohere: found and published the behaviour, the trace and the prefix; "less than one call in 100,000"; "URL generation
  jumps from 4 to 92 percent" with -o; "a bare cloud metadata address such as 169.254.169.254 in 23 to 36 percent of
  completions" at early prefill points. Cohere's article does not mention quantization or the serving provider.
- XDA Developers (Adam Conway): the routify host in "roughly four in ten final answers", the AccessKey ID, and the n-gram
  masking explanation. XDA's article does not discuss quantization.
- This work adds: the same prefix across files and placement, the decision-point odds, and the table comparison.

## The follow-up (2026-10-31)

Same three setups. Receipt: Addendum 4 in `RESULT_FLASHNEXT_PROBE.md`.

"Decoded" below means single-stream, one token per step, no speculation, on this build, on P100s. A four-token batch already lands on
the prefilled side, so speculative decoding and busy multi-user serving are covered by neither column. Cohere's stack was not tested.

1. Prefilling is not a neutral probe. Same tokens, same file, same placement, prefilled of 400 -> decoded of 100, at the batch 1 cut:

| | IQ4_XS, 44 | Q2_K_XL, 44 | Q2_K_XL, all GPU |
|---|---|---|---|
| watchlist: aliyuncs or routify (registered) | 7 -> 9 | 15 -> 11 | 7 -> 8 |
| 100.100.100.200 (registered) | 21 -> 5 | 29 -> 0 | 9 -> 1 |
| routify-sg first host (post hoc) | 0 -> 8 | 11 -> 9 | 1 -> 6 |
| first host starts 23. (post hoc) | 0 -> 0 | 260 -> 42 | 141 -> 58 |

2. The tool call after "without tool calls", P(tool call next). The two files move in opposite directions. The decoded row is a reading,
   not sampled at this point:

| state | IQ4_XS, 44 | Q2_K_XL, 44 | Q2_K_XL, all GPU |
|---|---|---|---|
| prefilled | 6.4% | 61% | 70% |
| decoded | 32% | 0.28% | 2.0% |

3. Decoded, the metadata address nearly vanishes on the 2-bit file at 44 layers (the fall excludes 0), so there is little left for placement to
   move there: 7.3% vs 2.3% prefilled, 0 vs 1 of 100 decoded. Placement still shifts the distribution: first host 23. is 42 vs 58, the
   opposite way round from 65 vs 35.
4. Cohere's four prefill points on these GGUFs: a URL at 90-98% already at bare `curl -s` (Cohere 4%), so -o is not a switch here.
   Bare metadata IP 0 of 200 at every point (Cohere 23-36% early). The metadata address does appear, with a scheme: 2-7% early.
   Cohere's article gives neither the table's prefill text nor its settings, so the cause of the gap cannot be separated.
5. From the start of the command, curl or wget in 1 of 300 samples.

Limits: one trace, three setups, one engine, P100s, no full precision. n = 100 per decoded cell. The decoded state still replays Cohere's
text. None of these is a rate of the behaviour in use. Predictions that failed: -o as the switch, bare metadata surviving, and tool-call
odds of at least 1% on every setup.

## Correction note, draft for Mark to rework and post

A correction and a follow-up on my Flash-Next write-up.

The correction: the raw odds I gave for Cohere's sanmaohe bucket were wrong. My reader priced an odd spelling of the host, not Cohere's
tokens. In Cohere's own tokens it is at least about 1e-12 on the 4-bit file and about 3e-18 to 4e-18 on the 2-bit setups, not 4e-18 to
7e-38. Still 0 of 1,200 samples, and the rest of the table stands as measured.

The idea I floated was wrong too. Multiplying the odds along Cohere's recorded path only gives the probability of that one exact string, and
for a behaviour you would have to continue from samples that actually reached each stage. So I measured each point directly instead. From
the start of the command, my two files called curl or wget in 1 of 300 samples.

The follow-up: my percentages came from a prefilled cache. Decoding the same tokens one at a time, single stream with no speculation, moves
them a lot, and not in one direction. The odds of a tool call right after "without tool calls" go from 61% to 0.3% on the 2-bit file at 44
layers, but from 6% to 32% on the 4-bit file. Alibaba hosts rise from 2-4% to 8-11% on all three setups. The metadata address nearly vanishes
on the 2-bit file at 44 layers (29 of 400 to 0 of 100), so there is little left for placement to move there, but placement still shifts other
hosts, the opposite way round from before. Prefilled and decoded are different states. Even a four-token batch lands on the prefilled side here,
so this says nothing about speculative decoding or busy multi-user servers.

One trace, one engine, P100s, no full precision, 100 samples per decoded cell. Cohere's own stack was not tested. Receipts: LINK
