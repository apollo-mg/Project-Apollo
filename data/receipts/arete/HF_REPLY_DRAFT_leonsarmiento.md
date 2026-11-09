Thank you, this is exactly what I hoped someone would do. An independent replication on MLX, with your own question
set and two separately made base quants, is worth more than anything we could add from our side. The direction and
the signature match (one-directional flips toward confident fabrication, real-fact controls untouched), and your
second base quant scoring identically rules out the quantization pipeline far better than we did.

Your Sage-A1.5 result made me check our setup, and you caught a real flaw: our comparison had Sage at Q8_0 and the
base at a plain Q6_K, so precision was not matched the way it was for Arete. I reran it last night with Sage at Q6_K
from the same packager as the base file (mradermacher's static quants, every shared tensor the same type), same build,
same settings, prompts token-identical, plus a replay of the base that came out byte-identical to the original run.

Result: the gap holds. Sage refuses 48/100 invented items vs 67/100 for its base (-19 points, 95% CI -28 to -11), with
21 items flipping toward fabrication and 2 back. Knowledge is unchanged (64 vs 67 on hard real facts). So the precision
mismatch was worth about 3 points of our original -22, not the whole effect.

That leaves the disagreement between our sets open, and I'm curious about it. A few questions so we can line them up:
- Which Sage-A1.5 build and bit depth did you run, and what changed between the two inference profiles?
- Was your Qwen3.6 base the same release we used (Qwen/Qwen3.6-35B-A3B)?
- Our invented items are mostly novels (title plus a real author), universities and regional capitals; on Sage, 14 of
  the 21 flips were novels. What kinds of entities are in your 30?

The abliteration number is striking. 50% to 3% with zero flips back is the clearest case of the pattern I've seen.
