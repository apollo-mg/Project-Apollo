# Fact sheet: Qwen3.8-Flash-Next, the Cohere upload probe, and local GGUF files

For Mark to write from. Every number is in `RESULT_FLASHNEXT_PROBE.md` and its JSON files in this folder. ASCII only.

## The short version

1. The behaviour Cohere found carries into the GGUF files people download. Given Cohere's own half-written upload command,
   our local files finish it with a URL 395-400 times out of 400.
2. Where that URL points, and how often it is a cloud address, depends on the exact file and even on where five layers
   compute. The model sits on a near-tie between many destinations, and small numeric changes tip it.
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
| sanmaohe bucket | 4e-18 | 7e-38 | 2e-33 |

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
