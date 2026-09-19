# Finding -- a "3-bit" quant is 3.5 real bits, and the label spans 26%

**2026-09-19.** Measured from GGUF tensor tables, on scored bytes (file minus the MTP draft head
`llama-perplexity` ignores). Prompted by Mark's read that *"3 bit on the label is more like 3.5."*

It is.

## Label vs reality

| class | member | **real scored bpw** |
|---|---|---:|
| **ternary** | Bonsai 2 PTQ1_0 | 1.748 |
| | Bonsai 2 PQ2_0 | 2.119 |
| **2-bit** | GSQ-RCO IQ2_XS | 2.476 |
| | EXL3 *nominal 2.50* | 2.774 |
| | AD-IQ2_XS | 2.822 |
| | UD-Q2_K_XL | 2.862 |
| **3-bit** | GSQ-RCO IQ3_XXS | **2.968** |
| | EXL3 *nominal 3.00* | 3.221 |
| | AD-IQ3_XXS | 3.465 |
| | UD-IQ3_XXS | 3.518 |
| | AD-IQ3_S | 3.732 |
| | i1-IQ3_M | 3.737 |
| **4-bit** | EXL3 *nominal 4.00* | 4.115 |
| | UD-IQ4_XS | 4.125 |
| | UD-Q4_K_M | 4.726 |

**Spreads within a class: 2-bit 16%, 3-bit 26%, 4-bit 15%.**

## The 3-bit class, specifically

**Median 3.518 real bits. Four of six sit at 3.4 or above.** "IQ3" in practice means 3.0 to 3.7
real bits, usually around 3.5.

**Even the formats that publish a number understate it.** EXL3's *nominal* 3.00bpw measures 3.221
scored bpw (+7%), and its nominal 4.00 measures 4.115. A self-reported bpw is not the file's
actual cost either.

**One honest outlier: GSQ-RCO IQ3_XXS at 2.968 is the only genuinely sub-3-bit "IQ3" measured.**
ISTA-DASLab labels tightly where others pad. That does not rescue GSQ at matched size -- UD-Q2_K_XL
is both smaller (2.862) and better (0.0842 vs 0.1012) -- but it does mean **label-matched
comparisons have been systematically unfair to GSQ-RCO**, giving its competitors up to half a bit
of free headroom. Anyone quoting the GSQ result should quote it at matched *bytes*, not matched
label.

## Why this matters beyond pedantry

1. **Every label-keyed comparison compares different size classes.** A reviewer putting
   "GSQ IQ3_XXS" against "AD-IQ3_XXS" is comparing 2.968 against 3.465 bpw -- a 17% size
   difference -- and attributing the result to the codec.
2. **It makes "the floor is N bits" almost unfalsifiable as usually stated.** If a 3-bit label
   means anywhere from 2.97 to 3.74 real bits, "3-bit works now" can be true or false depending
   entirely on whose 3-bit you ran.
3. **It compounds with the MTP-head accounting.** A file's *label* misstates its bits, and its
   *size* misstates its scored bits, in the same direction for some packagers and not others.

This is [[gguf-label-is-not-a-spec]] promoted from a within-packager observation to a
cross-packager measurement: the memory recorded that stock/unsloth/bartowski ship three different
recipes under one label. Here the quantity is put on it -- **26% at the 3-bit label**.

## The practical rule

**Never compare by label. Measure the file, subtract what the measurement ignores, compare at
matched scored bytes.** Every finding in this campaign that looked surprising at the label level
(AD "beating" GSQ, for one) resolved once the real sizes were on the table.
