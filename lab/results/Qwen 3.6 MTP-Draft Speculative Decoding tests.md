Qwen 3.6 MTP-Draft Speculative Decoding Tests

Qwen3.6-27B-uncensored-heretic-v2-Native-MTP-Preserved-Q4_K_M.gguf (16.0 GB)
Dual P100's


Warmup Prompt:
prompt eval time =   46230.93 ms /  4736 tokens (    9.76 ms per token,   102.44 tokens per second)
       eval time =    8510.96 ms /   112 tokens (   75.99 ms per token,    13.16 tokens per second)
      total time =   54741.89 ms /  4848 tokens
draft acceptance rate = 0.35802 (   58 accepted /   162 generated)

Fastest prompt during multi-turn agentic run:
prompt eval time =    1041.68 ms /    39 tokens (   26.71 ms per token,    37.44 tokens per second)
       eval time =    3614.23 ms /    87 tokens (   41.54 ms per token,    24.07 tokens per second)
      total time =    4655.90 ms /   126 tokens
draft acceptance rate = 0.92754 (   64 accepted /    69 generated)


4.13.250.403 I statistics draft-mtp: #calls(b,g,a) = 7 411 411, #gen drafts = 411, #acc drafts = 309, #gen tokens = 1233, #acc tokens = 696, dur(b,g,a) = 0.006, 6669.766, 0.633 ms
4.13.250.637 I slot      release: id  0 | task 411 | stop processing: n_tokens = 3127, truncated = 0

Qwen3.6-35B-A3B-UD-IQ4_NL-MTP.gguf (17.3GB)

Warmup Prompt:
prompt eval time =   26287.55 ms /  4736 tokens (    5.55 ms per token,   180.16 tokens per second)
       eval time =    3119.89 ms /   107 tokens (   29.16 ms per token,    34.30 tokens per second)
      total time =   29407.44 ms /  4843 tokens
draft acceptance rate = 0.46667 (   63 accepted /   135 generated)
2.52.625.460 I statistics draft-mtp: #calls(b,g,a) = 1 45 45, #gen drafts = 45, #acc drafts = 32, #gen tokens = 135, #acc tokens = 63, dur(b,g,a) = 0.002, 444.807, 0.034 ms

Fastest prompt during multi-turn agentic run:
prompt eval time =   13479.45 ms /  2678 tokens (    5.03 ms per token,   198.67 tokens per second)
       eval time =    3529.68 ms /   185 tokens (   19.08 ms per token,    52.41 tokens per second)
      total time =   17009.12 ms /  2863 tokens
draft acceptance rate = 0.89333 (  134 accepted /   150 generated)
3.28.817.172 I statistics draft-mtp: #calls(b,g,a) = 3 204 204, #gen drafts = 204, #acc drafts = 166, #gen tokens = 612, #acc tokens = 391, dur(b,g,a) = 0.004, 1975.546, 0.163 ms
