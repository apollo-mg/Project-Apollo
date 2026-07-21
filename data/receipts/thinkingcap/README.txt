# ThinkingCap forensic + brevity receipts
harvested: 2026-07-20T18:29:39+00:00   host: ai-supermicro-server  (10.0.0.194)
measured:  2026-07-15 .. 2026-07-17

## what these files establish
1. TENSOR FORENSIC (tc_tensor_forensic.log): byte-level hash comparison of
   ThinkingCap vs stock Qwen3.6-27B, tensor by tensor.
   - MTP head (blk.64 + nextn.*, 15 tensors): BYTE-IDENTICAL embedded vs standalone
   - body vs stock: 573/851 tensors byte-identical
   - diffs: FFN on all 64 layers; attn q/k/v/o on exactly the 16 full-attention
     layers (arch is a 3:1 SSM:attention hybrid); ssm_a on 22/48 linear layers
   - ssm_a is NOT a LoRA target -> real trained decay changes, NOT a pure LoRA merge.
     This is the load-bearing result: the model is genuinely trained, not a cheap merge.

2. BREVITY A/B (brevity_analysis.txt): 80 paired generations, matched Q8_0 quant,
   thinking forced on, identical prompts and sampling on both arms.
   - think tokens: geo-mean tc/stock = 0.783 (-22%), paired t=-7.97, sign-p 4.65e-10
   - answer tokens: geo-mean 0.830 (-17%), t=-8.53, sign-p 7.53e-10
   - stock hit the 3072-token cap 13/80; ThinkingCap 0/80
   - censored pairs excluded from the paired stats (67 clean pairs used)

## honest limits
- Head-vs-stock MTP leg rests on pwnstar's Unsloth check: our stock Q8_0 carries
  no MTP tensors, so we could not diff that leg locally.
- OPEN AXIS: accuracy under thinking-on is NOT measured here. Brevity is established;
  whether the shorter reasoning costs correctness is unresolved.
- Brevity was measured at Q8_0 only; other quant tiers untested.

## hardware
index, name, memory.total [MiB], clocks.current.sm [MHz], clocks.current.memory [MHz], power.limit [W]
0, Tesla P100-PCIE-16GB, 16384 MiB, 1063 MHz, 715 MHz, 150.00 W
1, Tesla P100-PCIE-16GB, 16384 MiB, 1063 MHz, 715 MHz, 150.00 W
2, Tesla P100-PCIE-16GB, 16384 MiB, 1063 MHz, 715 MHz, 150.00 W
3, Tesla P100-PCIE-16GB, 16384 MiB, 1063 MHz, 715 MHz, 150.00 W

## file inventory
      2814  brevity/analyze_brevity.py
       659  brevity/brevity_analysis.txt
      2120  brevity/brevity_gen_stock.log
      2117  brevity/brevity_gen_tc.log
      5234  brevity/brevity_runner.log
      8414  brevity/brevity_stock.jsonl
      8359  brevity/brevity_tc.jsonl
      5536  brevity/gen_brevity.py
      2023  brevity/run_tc_brevity.sh
      4611  digests/brevity_server_stock.digest.txt
      4607  digests/brevity_server_tc.digest.txt
      5850  forensic/kld_thinkingcap_q8.log
      1062  forensic/run_tc_forensic.sh
       552  forensic/tc_forensic_runner.log
     25956  forensic/tc_tensor_forensic.log
      3835  forensic/tc_tensor_forensic.py
     31054  forensic/thinkingcap_dl.log
      1986  README.txt
