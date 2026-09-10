# DRAFT — reply to jabba re: Flash-Next gibberish. For Mark. NOT SENT.

---

Ran your model on the P100 box to get you a control. **Same quant** (`Qwen3.8-Flash-Next-UD-IQ4_XS`),
buun's tree, and it generates fine — so it's not the model or the arch.

Two arms, both coherent, temp 0:

```
-c 8192 -ngl 99 -fa on --jinja -np 1 -fit off -ncmoe 24
  "The capital of France is Paris. It is historically significant as a major center of
   European politics, culture, and intellectual life..."

  ... + --chat-template-file <buun's qwen3.6 template>
  "The capital of France is Paris, a city whose historical significance spans over two
   millennia. Originally settled by the Celtic Parisii tribe..."
```

So the 3.6 template override isn't your problem either — I tested it specifically because it
looked suspicious, and it works.

**My guess is your build predates the fixes.** buun announced qwen4 support here on the 30th, but
he kept committing after that:

```
08-30 18:11  97474a38b  qwen4: add optimized inference, MTP, and VBR support
08-30 21:09  295850adc  fix(qwen4): restore Turbo V output in sparse attention
   <-- announcement was right about here
08-31 17:05  fd56dfcdd  qwen4: harden adaptive caching and long-context paths
08-31 19:53  6a2eb3232  qwen4: fix recurrent PLE speculative resize
08-31 22:00  87b37eac9  speculative: align MTP context sizing and fit
09-01 11:39  0f6a7267a  fix(qwen4): unrotate Turbo K after QSA gather
09-01 19:22  2d5ef7910  qwen4: support official shared MTP sidecars
```

If you built on the announcement you're missing four qwen4 correctness fixes. The two `fix(qwen4)`
ones are literally "output comes out wrong" bugs — K and V left in the rotated storage domain, so
attention reads garbage. That is exactly "generates gibberish".

`fd56dfcdd` ("harden adaptive caching and long-context paths") also looks relevant given you were
at `-c 512000`.

What does `git log --oneline -1` say in `/mnt/storage/Projects/buun-llama-cpp`? I'm on
`7a918624b`. If you're anywhere before `0f6a7267a`, a pull and rebuild is the first thing to try.

Two smaller things while I was in there:

- The GGUF says `qwen4exp.context_length = 262144` and carries **no rope-scaling metadata**, so
  `-c 512000` is running ~1.95x native with no YaRN. Probably not what's biting you since you see
  it at 8192 too, but worth pinning to 262144 anyway.
- The GGUF ships its own chat template and it's multimodal (image/video aware). The 3.6 one you're
  pointing at works, but you're giving up whatever 3.8-specific structure is in the shipped one.
