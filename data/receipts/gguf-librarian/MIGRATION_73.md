# .73 REAP ladder migration — verified before deletion

2026-08-13. 7 models, 94.5 GiB, moved .73 -> //10.0.0.43/mgalyan/Models/reap_ladder.
These were the ONLY copies in the fleet: a cross-host census confirmed 0 of 7
existed on the NAS, so a clear-before-copy would have been unrecoverable.

Verification: exact byte size + sha256 of the first and last 16 MiB, both sides.
Size alone is insufficient — SMB truncation and bit corruption both preserve length.

```
size            head_sha256_16MiB                 tail_sha256_16MiB                 file
13034400800	56c060bf5666c6b37177f24fe1d53db3	b25232b4a39c91bd3fec5b5154fe1172	FB-BASE-Q3_K_S.gguf
13140893152	d387cd266dc1806dc70ea22ed711a55c	38fce4d6b0d9809c6b395621d5b6b685	FB-REAP09-Q3_K_M.gguf
12901193760	a54f89430e7eba5564d5eb9751285c25	09dfe86f5ee17e08f265ec7db8e6d024	FB-REAP19-Q3_K_L.gguf
13193584800	a509244fc95400fa763344fd464b493f	477044c8e74ae1414708ceaa47bfe052	FB-REAP39-Q5_K_S.gguf
20336984096	d70678cf1994fcbe3316395469ff6cf1	8409df52d20c3ef3df8ccb9edb062360	GLM-4.7-Flash-REAP-19-Q6_K.gguf
15702701216	0d452774a5b43ab3341ae5d85f70b79a	025f68c8beeda5054aa3783430d54fee	GLM-4.7-Flash-REAP-39-Q6_K.gguf
13207318240	ff0841406a2dd0e4dbf331ddc9ecc214	de27a534b7261d4127cfb240f81a6040	GLM-4.7-Flash-REAP-50-Q6_K.gguf
```

All 7 matched. .73 then cleared: 84% -> 40% used (132 GB free), 0 GGUF >1 GiB remaining.

## Why these matter

- `FB-BASE` + `FB-REAP09/19/39` are the model set behind `RESULT_REAP_DOSE_RESPONSE.md`.
  Each variant is pruned independently from the unpruned base (confirmed by Akicou),
  not cascaded, so regenerating the ladder means re-pruning, not re-downloading.
- The three `GLM-4.7-Flash-REAP-*-Q6_K` are the only models in the fleet that clear
  every MoE-cache gate stock: single Q6_K expert type, 2520 KiB/expert (2.5x the
  pre-Ampere floor), and inside the Vulkan/Metal 4-type set. They are the test case
  for whether the ~2x P100 result holds without forcing GGML_CUDA_MOE_CACHE_MIN_EXPERT_KB.
