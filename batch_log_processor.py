import os
import sys
import argparse

def chunk_text(text, max_words=1500):
    """Splits text into chunks of approximately max_words, respecting line breaks."""
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = []
    current_length = 0
    
    for p in paragraphs:
        words = len(p.split())
        if current_length + words > max_words and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            current_chunk = [p]
            current_length = words
        else:
            current_chunk.append(p)
            current_length += words
            
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
        
    return chunks

def main():
    parser = argparse.ArgumentParser(description="Chunk 48h chat logs for local LLM ingestion.")
    parser.add_argument("--input", type=str, default="/mnt/TG_2TB/Projects/Apollo/gemini_48h_transcript.md", help="Input markdown file.")
    parser.add_argument("--output-dir", type=str, default="/mnt/TG_2TB/Projects/Apollo/log_chunks", help="Directory to save chunks.")
    parser.add_argument("--words", type=int, default=1500, help="Approximate word count per chunk.")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file {args.input} not found.")
        sys.exit(1)
        
    with open(args.input, 'r') as f:
        text = f.read()
        
    chunks = chunk_text(text, max_words=args.words)
    total_chunks = len(chunks)
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Divided log into {total_chunks} chunks.")
    print("=" * 50)
    print("🧠 STRATEGY: Sequential Ingestion Protocol")
    print("=" * 50)
    print("1. Set your local agent (e.g., DeepSeek-R1 or Llama) with this SYSTEM PROMPT:\n")
    print(f'   "You are an expert technical auditor analyzing a multi-part chat log transcript. I will send you {total_chunks} parts. ' 
          'For each part, extract hard facts (bugs, file paths, configurations, decisions) into your internal thoughts. ' 
          'Do NOT summarize yet. Reply EXACTLY with: \'[ACK] Part X received. Ready for next.\'"')
    print("-" * 50)
    
    for i, chunk in enumerate(chunks, 1):
        chunk_file = os.path.join(args.output_dir, f"chunk_{i:02d}.txt")
        with open(chunk_file, 'w') as f:
            if i == 1:
                f.write(f"PART {i}/{total_chunks}:\n\n{chunk}\n\n")
            elif i == total_chunks:
                f.write(f"PART {i}/{total_chunks} (FINAL PART):\n\n{chunk}\n\n" 
                        f"INSTRUCTION: This is the final part. Now, review all your extracted notes and " 
                        f"generate a comprehensive chronological summary of the last 48 hours, highlighting " 
                        f"engineering milestones, resolved bugs, and pending tasks.")
            else:
                f.write(f"PART {i}/{total_chunks}:\n\n{chunk}\n\n")
                
        print(f"Saved: {chunk_file}")
        
    print("-" * 50)
    print(f"To automate this, you can loop through the files in {args.output_dir} and pipe them into `llm_interface.py` or your Ollama CLI.")

if __name__ == "__main__":
    main()
