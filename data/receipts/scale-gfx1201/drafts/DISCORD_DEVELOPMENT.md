# Draft for Atlas Cybernetics Discord, #development

ASCII only. Follows the table already posted 2026-09-17 12:53 PM.

Two versions. Pick one.

---

## Version A -- short, conversational (recommended for a chat channel)

Ran both #1119 defects on 1.7.3 to see if either had been fixed upstream. Neither has, so
the #1107 workarounds need to stay.

Board here is an RX 9070 XT, so 16 GB consumer gfx1201 rather than the 32 GB R9700. Same
ISA, different memory regime, and a desktop session on the card.

cudaMemGetInfo: exactly the 4.00x you measured. I swept chunk size (4 / 11 / 32 MiB) and the
overhead scales with the request while the ratio stays pinned, so it is a clean multiplier
and not fixed bookkeeping per allocation. Reachable fraction is flat at about 24.6% of the
board across the whole sweep.

Two things that might save someone time:

- The free counter does not reach zero. It pins at 56.25 MiB and then 337 more allocations
  succeed while it sits there. Anything checking `free == 0` will miss this. I wrote exactly
  that bug into my own probe first and it cheerfully reported a clean run.
- "No recovery" looks process-scoped. In-process I get 48.5% restored, matching you, but
  after exit sysfs goes back to baseline. So it reads like runtime accounting rather than a
  leak, which Spectral will triage differently.

cuModuleGetFunction: identical trace, success plus a non-NULL handle, failure deferred to
launch as INVALID_IMAGE. One addition, `cuModuleGetGlobal` on an absent global *does* fail
at lookup. So the two module lookup paths disagree and the function path is the odd one out,
which is a more specific thing to hand upstream.

One I could not reconcile: the 22064 figure in the issue does not fit a clean 4x on a 32 GB
board, which should pin near 7.9 GiB. I suspect it is where the loop stopped rather than
where the counter pinned. If someone has the raw trace I would like to check that before it
goes to Spectral, since it is the one number in the report I cannot reproduce.

Also, unrelated but it cost me an hour: SCALE 1.7.3 does not compile at all against glibc
2.41+. Its builtins.h declares `__host__ __device__ double rsqrt(double)` and modern glibc
exposes rsqrt/cospi/rootn/powr as C23 math whenever _GNU_SOURCE is set, which clang does
automatically for C++. Invisible on Ubuntu and Rocky. Anyone on Arch or Rawhide will hit a
wall immediately.

Probes are standalone, SPDX, no Atlas build or weights needed. Happy to PR them under
scripts/scale-probe/ or just hand them over, whichever is less trouble.

---

## Version B -- one-liner plus link, if you would rather not wall-of-text the channel

Followed up on the table: ran both #1119 defects against SCALE 1.7.3 on a 16 GB consumer
gfx1201 (9070 XT). Neither is fixed, so the #1107 workarounds stay. cudaMemGetInfo is a
clean 4.00x multiplier (verified by sweeping chunk size, not just the 11 MiB case) and the
free counter pins at a nonzero floor while allocations keep succeeding, which is worth
knowing if anyone automates a check for it. cuModuleGetFunction reproduces exactly, and
cuModuleGetGlobal does *not*, which narrows where the bug lives. Full writeup and standalone
repros here: <link>

Happy to drop the details in thread if useful.

---

## Notes before posting

- Version A assumes the channel is fine with long technical posts. The screenshot you
  already posted got engagement, so probably yes.
- Neither version mentions the ownership dispute, the fork, or Azeez. Keep it that way.
- The 22064 question is the one genuinely useful ask in here. It invites a correction rather
  than asserting one, which is the right posture given you are the new person in the channel.
- If you want to stay fully neutral on repo politics, Version B plus a link to your own
  writeup keeps the artifact yours and does not put content into their tree.
