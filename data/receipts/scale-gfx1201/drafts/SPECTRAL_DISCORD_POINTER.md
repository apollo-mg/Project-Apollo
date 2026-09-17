# Discord heads-up -- post after the three GitHub issues are filed

Short by design. The detail lives in the tickets; this is a signpost so it is visible in the
channel without pasting walls of text. Fill in the three issue numbers before posting.

---

Hi all. Filed three tickets on the GitHub tracker after testing SCALE 1.7.3 on a Radeon RX 9070 XT
(gfx1201, RDNA 4, 16 GB consumer board) rather than the workstation parts these usually get tested
on. Putting a pointer here since I gather the channel is where a lot of this gets discussed.

- #___ `cudaMemGetInfo` charges exactly 4.00x the requested bytes, then the free counter saturates
  at a nonzero floor while allocations keep succeeding. Verified as a multiplier rather than fixed
  overhead by sweeping chunk size across an 8x range.
- #___ `cuModuleGetFunction` returns `CUDA_SUCCESS` with an unusable handle for symbols the module
  does not define. `cuModuleGetGlobal` correctly fails at lookup, so the two paths disagree.
- #___ SCALE 1.7.3 will not compile against glibc 2.41+ at all -- `builtins.h` collides with the
  C23 math declarations. Invisible on Ubuntu and Rocky, blocks Arch and Fedora Rawhide entirely.
  This one is probably the most impactful for new users since nothing compiles.

Standalone reproducers attached to each, SPDX Apache-2.0, needing only SCALE and a GPU. The first
two were originally reported against 1.7.1 on an R9700 by the Avarok Atlas project
(Avarok-Cybersecurity/atlas #1119); this confirms both still reproduce on 1.7.3 on very different
hardware.

One disclosure up front: my box runs the upstream amdgpu driver rather than the DKMS package, so
`scalediag` flags a KFD ioctl check. I have covered in the tickets why I do not think that explains
either runtime result, but happy to be told otherwise, and happy to re-run on a supported
configuration if that helps.
