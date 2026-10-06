# One MTP call

Same `prose.txt` on both sides. One server, one recorded chat call. The JSON is the comparison.

```
llama-server -m TARGET --model-draft DRAFT \
  --spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-p-min 0 \
  --reasoning off -ngl 99 -c 262144 -fa on -np 1 --metrics --no-webui \
  --host 127.0.0.1 --port 18081
```

```
python3 capture_gemma4_mtp_receipt.py \
  --base http://127.0.0.1:18081 \
  --prompt prose.txt --target TARGET --draft DRAFT \
  --argv "llama-server -m TARGET --model-draft DRAFT --spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-p-min 0 --reasoning off -ngl 99 -c 262144 -fa on -np 1 --metrics --no-webui --host 127.0.0.1 --port 18081" \
  --out receipt.json
```

Send `receipt.json` back. It is one warmup plus one measured call. The file also reads `/props`, `/apply-template`, and `/tokenize`. Those do not generate tokens.

What the JSON is for:

- `files.target_sha256` and `files.draft_sha256` say whether the GGUF bytes match. The Q8 draft we have is sha256 `145db9094bc0f85f1701e255a2ed216dcc9800fc8bc8631ad00905b456bd451b`, 465109248 bytes.
- `rendered_prompt_token_ids` is the chat template the server actually fed the model. `prompt_token_ids` is the raw file. `template_extra_tokens` is the difference. `rendered_prompt_prefix` and `reasoning_content_chars` show whether thinking was on.
- `server_settings` is the speculative, reasoning, and cache fields the server reports. `engine.props_build` is the build. `engine.chat_template` is a hash of the template, not the template text.
- `measured` is tok/s, draft accepted/drafted, accept rate, tokens per pass, and milliseconds per pass. `position_hits` comes from `/metrics` for that one call.

Python 3 stdlib only.

