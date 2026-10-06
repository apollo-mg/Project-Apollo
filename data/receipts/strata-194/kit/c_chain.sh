#!/usr/bin/env bash
# PREREG_STRATA_194_Q4XL Addendum C (on .194, detached): UD-IQ4_XS on one card, Strata vs buun + MTP.
cd "$(dirname "$0")"
L=$PWD/runs/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
R=$PWD/canonical_reasoning-v1.txt
CFG=$HOME/strata/strata-iq4-1card.json
python3 - "$HOME" > $CFG <<'PY'
import json, sys
h = sys.argv[1]
c = json.load(open(f"{h}/strata/strata-unsloth-ud-q4_k_xl.json"))
a = c["args"]
a[a.index("--pack") + 1] = f"{h}/strata-data/packs/unsloth-ud-iq4_xs"
a[a.index("--native") + 1] = f"{h}/strata-data/models/unsloth-UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf"
a[a.index("--resident-budget-gib") + 1] = "55"
c["tokenizer"] = f"{h}/strata-data/packs/unsloth-ud-iq4_xs/tokenizer"
c["log"] = f"{h}/strata/strata-iq4-1card.log"
c["model_name"] = "qwen3.8-flash-next-unsloth-ud-iq4_xs-1card"
print(json.dumps(c, indent=1))
PY
cp $CFG runs/strata_config_iq4_1card.json; log "C: config written, gpu=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["gpu"])' $CFG)"
export STRATA_CFG=$CFG HFID=unsloth/Qwen3.8-Flash-Next-GGUF QUANT=UD-IQ4_XS
export LLAMA_MODEL=$HOME/strata-data/models/unsloth-UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf
MTP="-md $HOME/AI/Models/flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3"
F1="-fa on -fit on -fitt 4096 -lv 4"; SPEC="--spec-method mtp --spec-num-tokens 3"
./run194.sh strata C_S1_r1 $R ""
CUDA_VISIBLE_DEVICES=0 ./run194.sh llama C_B1_r1 $R "$F1 $MTP" $SPEC
./run194.sh strata C_S1_r2 $R ""
CUDA_VISIBLE_DEVICES=0 ./run194.sh llama C_B1_r2 $R "$F1 $MTP" $SPEC
[ -f $HOME/strata/strata-iq4-1card.log ] && cp $HOME/strata/strata-iq4-1card.log runs/strata-engine-iq4-1card.log
log C_DONE
