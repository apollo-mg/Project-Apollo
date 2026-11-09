Thank you, this is exactly what I hoped someone would do. An independent replication on MLX, with your own question
set and two separately made base quants, is worth more than anything we could add from our side. The direction and
the signature match (one-directional flips toward confident fabrication, real-fact controls untouched), and your
second base quant scoring identically rules out the quantization pipeline far better than we did.

Your Sage-A1.5 result disagrees with ours, and I think that's the most useful part of your reply. On M1 we had Sage
refusing 45/100 invented items against 67/100 for its base, greedy, thinking off, byte-identical prompts. But our
comparison had a mismatch I should have flagged: Sage was Q8_0 and the base was a plain Q6_K, so we did not match
precision the way we did for Arete. Your data says Sage holds its base's rate, and if that's right, our -22 is at
least partly a setup artifact, and "fine-tuning doesn't have to cost honesty" has a second example besides adapters
trained on "I don't know".

A few questions so we can line the two up:
- Which Sage-A1.5 build and bit depth did you run, and what changed between the two inference profiles?
- Was your Qwen3.6 base the same release we used (Qwen/Qwen3.6-35B-A3B)?

On our side, I'm rerunning Sage at Q6_K from the same packager as the base file we already ran (mradermacher's
static quants), same build, same settings, with a same-day replay of the base as a control. I'll post the result here
either way.

The abliteration number is striking. 50% to 3% with zero flips back is the clearest case of the pattern I've seen.
