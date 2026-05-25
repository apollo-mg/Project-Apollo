


How to Update TheTom's llama.cpp Fork:

# 1. Go to your local engine folder
cd /mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant

# 2. Wipe the old unstaged edits and pull TheTom's absolute newest code
git restore .
git checkout feature/turboquant-kv-cache
git pull origin feature/turboquant-kv-cache

# 3. Re-apply your custom ROCm memory patch (this stops the 110k context OOM crash)
git apply my_rocm_fattn_fixes.patch

# 4. Configure CMake specifically for your RDNA4 card
# Notice the gfx1201 target and the ROCWMMA flag for faster attention math!
HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
cmake -S . -B build \
    -DGGML_HIP=ON \
    -DAMDGPU_TARGETS=gfx1201 \
    -DGGML_HIP_ROCWMMA_FATTN=ON \
    -DCMAKE_BUILD_TYPE=Release

# 5. Compile the binaries (using all your CPU cores to make it fast)
cmake --build build --config Release -- -j $(nproc)

  What these commands actually do:
  * git restore .: This throws away those old, manual C++ edits you made months ago so Git doesn't yell at you when you try to pull new code.
  * git apply: This cleanly pastes your custom hip_f16_alloc memory pooling fix back onto the newest version of the code.
  * HIPCXX and HIP_PATH: These environment variables explicitly tell the compiler where your CachyOS ROCm installation lives so it doesn't accidentally use a generic CPU compiler.
  * DAMDGPU_TARGETS=gfx1201: This forces llama.cpp to compile the math kernels explicitly for the RX 9070 XT. If you don't include this, it tries to compile for every AMD card ever made,
      which takes 45 minutes and wastes disk space!
  * DGGML_HIP_ROCWMMA_FATTN=ON: Because you have a modern (RDNA4) card, this enables AMD's hardware-accelerated matrix multiplication for the Flash Attention math, significantly speeding up
      prompt processing.
