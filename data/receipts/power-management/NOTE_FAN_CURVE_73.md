# Note -- .73's blower curve, inferred from the cards: one speed through 19 minutes of full load, 51-55 C at 300 W; and the daily driver fails on 3 concurrent requests (VRAM)

**2026-09-30.** A diagnostic Mark asked for ("see how I have the fan curve triggered so I don't have to hook up a video
cable and look in BIOS"). Not pre-registered. Driver `fan_curve_probe.py`, raw `fan_curve/samples.csv` (2 s samples),
`fan_curve/phases.json`.

**Setup:**
- .73's two Tesla P100s are air-cooled: each has a 3D-printed duct and a 24 V 120 mm GDSTime blower.
- The blowers are fed from an external 24 V supply through a MOSFET driven by a motherboard fan header, which a BIOS
  (Smart Fan) curve controls.
- Linux cannot read that header: no Super I/O driver binds (`it87` finds no device; `gigabyte-wmi` loads and binds
  nothing). So blower speed is inferred from the cards.
- 150 W cap, 1328 MHz; daily driver (Qwen3.8-27B Q6_K, MTP, `-sm tensor`), one generation stream at ~22 tok/s.

## Results

| phase | GPU 0 | GPU 1 | GPU power | CPU package |
|---|---:|---:|---:|---:|
| idle | 33 C | 35 C | 72 W | 49-51 C |
| GPU load, minutes 4-6 | 50.7 C | 53.3 C | 295 W | 57 C |
| GPU + CPU load (8 threads on spare cores), last 2 min | 52.0 C | 54.2 C | 292 W | 65 C |
| GPU load again, last 2 min | 52.4 C | 55.0 C | 293 W | 61 C |

- **Peak 55 C** in 19 minutes of load. Slowdown is 82 C and shutdown 85 C, so there is 27 C of margin.
- **The blowers did not respond to CPU temperature.** +8 C on the CPU at constant GPU power left the cards where they
  were (they drifted up 1 C).
- **The blowers ran at one speed for the whole run.** The heating and cooling time constants match:

| | GPU 0 | GPU 1 |
|---|---:|---:|
| heating, first 110 s | 30.5 +/- 1.5 s | 32.1 +/- 1.5 s |
| cooling, first 110 s | 28.4 +/- 1.3 s | 31.3 +/- 1.6 s |

  A blower step during the load would shorten the cooling constant and put a dip in the heating trace; neither appears.
- **Thermal resistance at that speed** is about 0.14 C/W per card (33 -> 49 C for +111 W). Extrapolated to an
  uncapped 250 W card: about 66 C, still under slowdown, at this room temperature.

**Reading:** Mark recalls setting two speeds (idle, and full at a conservative temperature) on a GPU-reactive source,
possibly the PCIEX16 board sensor. That fits: the idle speed alone holds full capped load at 51-55 C, and the step to
full speed was never reached. **The step has therefore not been shown to work.**

## The weak point is power, not the curve

The blowers' 24 V comes from a 3D-printer supply next to the PC. If that supply is off while .73 runs, the cards have no
airflow. A software watchdog on GPU temperature (lower the power limit or stop the server at ~75 C) would cover that
and any blower failure. Not built yet.

## Side finding: 3 concurrent requests fail on the daily driver

The first attempt drove 3 parallel generations. **Every request returned HTTP 500** (`samples_attempt1_3streams.csv`,
`server_oom_excerpt.txt`):

```
E ggml_backend_cuda_graph_compute: CUDA pool allocation failed (out of VRAM), failing graph compute
E srv        decode: Compute error. off = 0, n_batch = 2048, ret = -2
```

- The server runs `-np 4` with `--vbr-vram auto`: "KV budget auto (remaining VRAM, resolved by fit)". At idle GPU 0
  has 1.6 GB free and GPU 1 has 2.8 GB.
- A 3-sequence batch plus MTP does not fit, and all in-flight requests fail together. Also logged:
  `spec configure_ca: backend offload failed for seq_id=1; using CPU sampler`.
- One stream works. Two were not tested.
- So an overlap of Mark, a guest and the nightly daydream would give everyone errors. Next: `-ts` to even the free
  VRAM plus a fixed VBR budget that leaves compute headroom (BACKLOG N16).
