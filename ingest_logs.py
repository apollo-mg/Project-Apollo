#!/usr/bin/env python3
import os
import glob
import sys

# Import the local Sovereign Engine interface
from llm_interface import query_llm

CHUNKS_DIR = "/mnt/TG_2TB/Projects/Apollo/log_chunks"
OUTPUT_FILE = "/mnt/TG_2TB/Projects/Apollo/data/summary_48h.md"

def main():
    chunk_files = sorted(glob.glob(os.path.join(CHUNKS_DIR, "chunk_*.txt")))
    if not chunk_files:
        print(f"[!] No chunks found in {CHUNKS_DIR}. Please run batch_log_processor.py first.")
        sys.exit(1)

    total_chunks = len(chunk_files)
    print(f"[*] Found {total_chunks} chunks. Beginning Sequential Ingestion Protocol...")
    print(f"[*] This will utilize the newly expanded 65K context window on Gemma 4.")

    SYSTEM_PROMPT = (
        f"You are an expert technical auditor analyzing a multi-part chat log transcript. "
        f"I will send you {total_chunks} parts sequentially. For each part, extract hard facts "
        f"(bugs, file paths, configurations, decisions) into your internal thoughts. "
        f"Do NOT summarize yet. Reply EXACTLY with: '[ACK] Part X received. Ready for next.'"
    )

    messages = []
    final_summary = ""

    for i, chunk_file in enumerate(chunk_files, 1):
        print(f"\n[*] Sending Chunk {i}/{total_chunks}...")
        with open(chunk_file, "r") as f:
            chunk_text = f.read()
        
        # Query the local LLM. 
        # llm_interface automatically handles system message prepending and <think> stripping 
        # from the messages_override history array to prevent context poisoning.
        
        # Only allow large generation output on the final summary chunk to save context window space
        current_max_tokens = 8192 if i == total_chunks else 100
        
        response = query_llm(
            prompt=chunk_text, 
            system_message=SYSTEM_PROMPT, 
            messages_override=messages,
            max_tokens=current_max_tokens
        )
        
        print(f"[Agent] {response}")
        
        # Append to our persistent history for the next iteration
        messages.append({"role": "user", "content": chunk_text})
        messages.append({"role": "assistant", "content": response})

        # --- MIDPOINT COMPRESSION ---
        if i == 14:
            print(f"\n[*] Context limit approaching. Performing midpoint compression...")
            mid_sys = "You are the Sovereign Architect. Summarize the chat history into a dense, technical summary."
            mid_prompt = "Summarize all the technical discussions, architecture decisions, and events in the chat history so far into a dense, comprehensive summary. Retain all key facts."
            
            mid_response = query_llm(
                prompt=mid_prompt, 
                system_message=mid_sys, 
                messages_override=messages,
                max_tokens=8192
            )
            print(f"[Agent Midpoint] {mid_response[:150]}...")
            
            # Reset history to only the summary
            messages = [
                {"role": "user", "content": f"Here is the summary of the first half of the 48-hour period:\n\n{mid_response}"},
                {"role": "assistant", "content": "[ACK] Midpoint summary received and memorized. Ready for the next half."}
            ]
        # ----------------------------

        if i == total_chunks:
            final_summary = response

    print("\n[*] Initiating Final Reflection Pass...")
    reflection_prompt = (
        "Now that you have generated the chronological summary, perform a final reflection pass on the entire 48-hour period. "
        "Identify:\n"
        "1. The most critical architectural risk or technical debt incurred.\n"
        "2. The most important completed milestone for the Sovereign OS.\n"
        "3. The immediate next strategic step the user should take.\n\n"
        "Output this as a 'Strategic Reflection' section."
    )
    
    reflection_response = query_llm(
        prompt=reflection_prompt,
        system_message=SYSTEM_PROMPT,
        messages_override=messages
    )
    
    print(f"[Agent Reflection] {reflection_response}")
    
    final_output = final_summary + "\n\n---\n\n## Strategic Reflection\n\n" + reflection_response

    print("\n" + "="*50)
    print("🧠 FINAL SYNTHESIS & REFLECTION COMPLETE")
    print("="*50)
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(final_output)
    
    print(f"[*] Saved final 48h summary to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
