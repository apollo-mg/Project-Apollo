import time
import argparse
from vllm import LLM, SamplingParams

def benchmark(model_name, max_tokens=256, enforce_eager=False, tp_size=1):
    print(f"Loading {model_name}...")
    print(f"Settings: TP={tp_size}, Enforce Eager={enforce_eager} (False = HIP/CUDA Graphs Enabled)")
    
    # We lower gpu_memory_utilization and max_model_len slightly 
    # to leave room for HIP graph capture on 16GB VRAM
    llm = LLM(
        model=model_name,
        tensor_parallel_size=tp_size,
        enforce_eager=enforce_eager, 
        trust_remote_code=True,
        max_model_len=1024, 
        gpu_memory_utilization=0.75, 
        dtype="half",
        # enforce_eager=False captures graphs for specific batch sizes.
    )
    
    prompts = [
        "Write a highly optimized quicksort algorithm in C++.",
        "Explain the theory of relativity as if I were 5.",
        "Create a simple python web server using FastAPI.",
        "What are the best practices for system design?",
        "Write a script to scrape a website using beautifulsoup.",
        "Explain quantum entanglement with an analogy.",
        "Write a rust program to parse a JSON file.",
        "How do transformers work in machine learning?",
        "Write a regex to match an email address.",
        "Implement a simple neural network from scratch in PyTorch."
    ] * 2 # 20 prompts
    
    sampling_params = SamplingParams(temperature=0.7, top_p=0.95, max_tokens=max_tokens)
    
    print("Warming up (running a small batch to ensure HIP graphs are active)...")
    llm.generate(["Warmup prompt"] * 2, sampling_params, use_tqdm=False)
    
    print("Running benchmark...")
    start_time = time.time()
    outputs = llm.generate(prompts, sampling_params, use_tqdm=True)
    end_time = time.time()
    
    total_tokens = sum(len(output.outputs[0].token_ids) for output in outputs)
    duration = end_time - start_time
    throughput = total_tokens / duration
    
    print("\n" + "=" * 50)
    print(f"vLLM BENCHMARK RESULTS")
    print("=" * 50)
    print(f"Model: {model_name}")
    print(f"Total time: {duration:.2f} s")
    print(f"Total generated tokens: {total_tokens}")
    print(f"Throughput: {throughput:.2f} tokens/s")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="RedHatAI/DeepSeek-R1-Distill-Qwen-14B-FP8-dynamic", help="HuggingFace model ID or local path")
    parser.add_argument("--eager", action="store_true", help="Enforce eager execution (disable HIP graphs)")
    args = parser.parse_args()
    
    benchmark(args.model, enforce_eager=args.eager)
