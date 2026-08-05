# Pulsar ↔ llama.cpp tokenizer parity on sm_60 — 8/8 exact

**Stage 1 of the pulsar external-numerics panel.** Date 2026-08-03. Node `.73` (2× Tesla
P100-PCIE-16GB, sm_60). Model: `Hermes3.6-35B-A3B-Uncensored-Genesis-V6-APEX.gguf` (25.69 GB,
qwen35moe), the *same GGUF file* fed to both engines.

- pulsar `a7fc493` + 5 uncommitted (sm_60 port), `pulsar-cli -f <file> -n 1`, reading the
  `pulsar: prompt ids [...]` line.
- llama.cpp `~/buun_vbr/build/bin/llama-tokenize -f <file> --no-bos --no-escape`.

## Why this gate exists

Pulsar ships a **hand-written tokenizer**. Its only parity test, `crates/tokenizer/tests/hy3_parity.rs`,
compares against **ds4** — pulsar's own ancestor — never against llama.cpp. If the two engines
disagree on token IDs, any downstream logit comparison is meaningless, so this runs first.

## Result

| case | content class | tokens | verdict |
|---|---|---|---|
| c01_plain | plain ASCII English | 5 | PASS |
| c02_newlines | run of 4 consecutive `\n` | 3 | PASS |
| c03_cjk | Japanese/Han (`北京市の天気はどうですか`) | 5 | PASS |
| c04_code | Python w/ indentation + comment | 14 | PASS |
| c05_digits | integers, float, hex, exponent | 28 | PASS |
| c06_punct | em/en dash, guillemets, ellipsis, literal `\x27` | 16 | PASS¹ |
| c07_space | leading/internal/trailing spaces + tab | 8 | PASS |
| c08_emoji | emoji, flag, ZWJ family sequence, diacritics | 31 | PASS |

**8/8 exact ID-sequence match.** Newline runs and Han splitting are called out explicitly in
pulsar's tokenizer source (`lib.rs:928` cites llama.cpp PR 21343; `lib.rs:1341` the kimi-k2 Han
check) and both agree here.

¹ c06 initially reported FAIL. **The divergence was the harness, not either tokenizer** — see below.

## ⚠️ Methodology finding: llama.cpp expands escapes by default, pulsar does not

`llama-tokenize` applies `--escape` **by default**, so a literal backslash sequence in the input
is silently rewritten before tokenization. On c06 (file bytes `64 6f 6e 5c 78 32 37 74` =
`don\x27t`):

```
default:      14572,914,42064,579,12129,61574,12620,4444,1317,42080      (10 tokens; ''t' ''s')
--no-escape:  14572,3351,17,22,83,42064,3351,17,22,82,12129,…,42080      (16 tokens; '\x' '2' '7' 't')
pulsar:       14572,3351,17,22,83,42064,3351,17,22,82,12129,…,42080      (identical)
```

**Any cross-engine comparison must pass `--no-escape` to llama.cpp**, or every prompt containing a
backslash is compared against different text. This is a live trap for the logit stage.

## Limits

- One model / one vocab (qwen35moe). Says nothing about pulsar's Inkling, K3, Laguna, or dsv4
  chat-template paths, which have their own `ChatStyle` handling.
- Raw tokenization only. Chat-template application (`ChatStyle::*`, BOS/EOS policy, role markers)
  is **not** covered and is where template bugs usually live.
- Tokenization is CPU-side and arch-independent — this result carries **no** information about the
  sm_60 `__dp4a` polyfill. That is stage 2's job.

## Provenance

- `.73:~/tokparity/` — `c0{1..8}_*.txt`, `run.sh`, `parity.log`
- Related: `../../Apollo Docs/Pulsar_Engine_Findings.md`
