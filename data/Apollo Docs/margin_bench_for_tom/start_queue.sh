#!/bin/bash
"/mnt/TG_2TB/Projects/Apollo/data/Apollo Docs/margin_bench_for_tom/run_f16_anchor.sh" > "/mnt/TG_2TB/Projects/Apollo/data/Apollo Docs/margin_bench_for_tom/queue.log" 2>&1
ssh root@10.0.0.194 "cd /home/mark/kv-eval-pack-20260707/kld-panel && TYPES=turbo4 ./kv_kld_sweep.sh /home/mark/llama-cpp-turboquant/build/bin" >> "/mnt/TG_2TB/Projects/Apollo/data/Apollo Docs/margin_bench_for_tom/queue.log" 2>&1
