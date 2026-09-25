# buun's `--resume` (`2acf5b10f`) on .73: under `-sm tensor` the shutdown save aborts on the same meta-buffer assert; under `-sm layer` the save works (675 MB, 8.5 s for 9.2k tokens) but the restore is refused (`policy_mismatch`)

**2026-09-25 00:00-00:40, `.73`** (2x P100, sm_60, CUDA 12.4). buun `2acf5b10f` (his `exp/server-resume` work,
pushed 09-24; "I pushed a bit of the new stuff already"), built in a separate worktree (`~/buun-resume`,
`build_sm60_resume`, the daily build's cmake flags). The daily-driver flags throughout: `Qwen3.8-27B-Q6_K` + mmproj,
`-c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 1 -fa on --spec-type draft-mtp --draft-max 3
--kv-unified`. Harness: `split-prefill-73/resume_test.py` -> `split-prefill-73/raw/resume_test.jsonl`. Server logs:
`raw_resume_2acf5/*.log.gz` (home paths redacted).

`--resume`: "keep the slots' conversations across restarts and sleep: their KV state is saved at shutdown and
restored at startup". Here it is `--resume --resume-path /mnt/models/resume-test` (NVMe).

## Results

| test | split | outcome |
|---|---|---|
| A: the `-np 1` idle-reuse abort (`INCIDENT_73_NP1_IDLE_REUSE_ABORT`, V5) | tensor | **still aborts**, same assert (`ggml-backend-meta.cpp:1783`) |
| R: resume round trip | tensor | **the shutdown save aborts** on the same assert. Store 24 KB, restart installs 0 entries, turn 2 re-prefills 9,237 tokens |
| RL: resume round trip | layer | **save OK**; **restore refused**; turn 2 re-prefills 9,237 tokens |

**R: tensor-split shutdown stack:**

```
resume_capture_all -> resume_capture_slot -> resume_capture_artifact -> vbr_capture_host_payload
-> transfer_host_payload -> vbr_transfer_explicit_manifest -> llama_memory_recurrent::state_write_data
-> ggml_backend_meta_buffer_get_tensor -> GGML_ASSERT(size % row_stride == 0)
```

It is the third entry path to the same assert, after the `-np 4` idle capture and the `-np 1` restore. **One fix
(reading recurrent state out of a tensor-split meta buffer) would unblock all three on this box.**

**RL: layer-split save:** `{"outcome":"saved","n_tokens":9237,"tail_states":2,"bytes_written":675728840,
"t_ms":8553.671,"capture_ms":3751.292}`. The shutdown took 9.8 s end to end. That is about **73 KB per token**
including two recurrent tail states: a 25k-token Hermes conversation would be about 1.8 GB, and 100k about 7 GB.

**RL: layer-split restore:** `{"outcome":"failed","reason":"precision_refused","status":"unavailable",
"validation":"policy_mismatch","destination":"feasible_current","adopt":"internal_error","worst_steps":5,
"deficit":72704,"weight":32768}`. The restarted server would not adopt the saved precision state. A likely but
untested cause: `--vbr-vram auto` resolves a different budget on each start, so the saved degrade schedule is not
reproducible.

## What it means for .73

- `--resume` is exactly the missing piece: suspend unloads the model, and today every cached conversation is lost. It
  needs:
  - the tensor-split recurrent read fixed;
  - a restore that tolerates the auto-budget varying between starts (or a pinned `--vbr-vram`, to test).
- The wake proxy's suspend waits 8 s after `pkill`. A save of 8.5 s (9k tokens), more for real conversations,
  would be cut off by the suspend. **The proxy must wait for the process to exit** before suspending. That is a
  one-line change, to make when resume becomes usable.
- Store location: `/mnt/HDD` on .73 is a spinning 2.5" drive (~100 MB/s), so a 1.8 GB save would take ~20 s there.
  The NVMe has ~10 GB free.

## Not established

- One conversation size (9.2k tokens), one run per split mode.
- Whether a pinned `--vbr-vram` budget lets the restore validate.
- This is an in-progress branch; buun said he will look at the assert after his feature lands.
