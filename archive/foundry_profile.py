#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import time

# --- CONFIGURATION ---
FOUNDRY_ROOT = "/home/mark/gemini/foundry_configs"
IMAGE_NAME = "rocm/vllm-dev:rocm7.2_navi_ubuntu24.04_py3.12_pytorch_2.9_vllm_0.14.0rc0"
HF_CACHE = "/media/mark/TG 2TB/huggingface_cache"
WORKSPACE = "/home/mark/gemini"

def run_profiling(model_id, max_len=2048, utilization=0.75):
    """
    Automates the 'Foundry Profile' for a new model.
    Builds TunableOp CSV and warms up HIP Graphs.
    """
    model_slug = model_id.replace("/", "--")
    profile_dir = os.path.join(FOUNDRY_ROOT, model_slug)
    os.makedirs(profile_dir, exist_ok=True)
    
    csv_filename = f"tunableop_{model_slug}.csv"
    csv_path = os.path.join(profile_dir, csv_filename)
    
    print(f"
[FOUNDRY] Starting Profile for: {model_id}")
    print(f"[FOUNDRY] Target Profile Location: {profile_dir}")
    print(f"[FOUNDRY] Using Image: {IMAGE_NAME}")
    
    # Construct the Docker command
    # We use -e PYTORCH_TUNABLEOP_FILENAME to redirect the tuning results
    docker_cmd = [
        "sudo", "docker", "run", "--rm",
        "--name", f"foundry-tuning-{int(time.time())}",
        "--network=host",
        "--group-add=video",
        "--ipc=host",
        "--shm-size", "16G",
        "--cap-add=SYS_PTRACE",
        "--security-opt", "seccomp=unconfined",
        "--device", "/dev/kfd",
        "--device", "/dev/dri",
        "-e", "HSA_OVERRIDE_GFX_VERSION=12.0.1",
        "-e", "PYTORCH_TUNABLEOP_ENABLED=1",
        "-e", f"PYTORCH_TUNABLEOP_FILENAME=/workspace/foundry_configs/{model_slug}/{csv_filename}",
        "-v", f"{HF_CACHE}:/root/.cache/huggingface",
        "-v", f"{WORKSPACE}:/workspace",
        "-w", "/workspace",
        IMAGE_NAME,
        "python3", "-c", f"""
from vllm import LLM, SamplingParams
print(f'--- FOUNDRY: LOADING MODEL ---')
llm = LLM(
    model='{model_id}',
    max_model_len={max_len},
    gpu_memory_utilization={utilization},
    trust_remote_code=True,
    dtype='half'
)
print(f'--- FOUNDRY: WARMING GRAPHS & TUNING ---')
# A single dummy inference triggers the graph capture and TunableOp processing
prompts = ['Foundry calibration sequence start. Reasoning check. Hardware alignment.'] * 5
sampling_params = SamplingParams(temperature=0.7, top_p=0.95, max_tokens=128)
llm.generate(prompts, sampling_params)
print(f'--- FOUNDRY: PROFILE COMPLETE ---')
"""
    ]
    
    try:
        subprocess.run(docker_cmd, check=True)
        print(f"
[FOUNDRY] SUCCESS: Model {model_id} has been profiled.")
        print(f"[FOUNDRY] Hardware math library saved to: {csv_path}")
    except subprocess.CalledProcessError as e:
        print(f"
[FOUNDRY] ERROR: Profiling failed for {model_id}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apollo Foundry: Model Profiling Agent")
    parser.add_argument("model", help="HuggingFace Model ID or local path")
    parser.add_argument("--len", type=int, default=2048, help="Max context length (default: 2048)")
    parser.add_argument("--util", type=float, default=0.75, help="VRAM utilization (default: 0.75)")
    
    args = parser.parse_args()
    
    run_profiling(args.model, args.len, args.util)
