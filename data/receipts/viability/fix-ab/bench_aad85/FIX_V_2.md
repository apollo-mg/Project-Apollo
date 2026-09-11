| model                          |       size |     params | backend    | ngl | type_k | type_v | vbr_codec  | vbr_entry  |  vbr_floor | vbr_floor_explicit | vbr_vram_bytes | vbr_vram_explicit |  fa |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | -----: | -----: | ---------- | ---------- | ---------: | -----------------: | -------------: | ----------------: | --: | --------------: | -------------------: |
| qwen35 27B IQ3_S - 3.4375 bpw  |   9.72 GiB |    27.32 B | ROCm       |  99 |    vbr |    vbr | turbo      | f16        |   0.000000 |                  0 |              0 |                 0 |   1 |  tg128 @ d13000 |         25.29 ± 0.11 |

build: a334fc01e (11990)
