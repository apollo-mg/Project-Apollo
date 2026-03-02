import llm_interface
import buddy_agent
import json
import re
import requests

def run_system_2_test():
    test_query = "Jarvis, I'm setting up my Octopus Pro board. How should I wire my standard 12V Noctua fans to the fan headers for best performance?"
    
    print(f"\n[TEST QUERY]: {test_query}")
    print("-" * 50)

    # 1. Fetch data from vault
    print("\n[STEP 1: QUERY VAULT]")
    vault_context = buddy_agent.Toolbox.query_vault("Octopus Pro fan wiring 12V 48V")
    print(f"VAULT DATA LENGTH: {len(vault_context)}")
    print("-" * 50)

    # 2. PERFORM SYSTEM 2 SYNTHESIS (DeepSeek-R1)
    print("\n[STEP 2: SYSTEM 2 TECHNICAL SYNTHESIS (DeepSeek-R1)]")
    
    sys_msg = """You are the Compliance Mind (The Engineer). 
Your goal is to provide a Technical Synthesis based on the provided documentation.

CRITICAL SAFETY PROTOCOLS:
1. INTERNAL KNOWLEDGE VS RAG: You MUST compare documentation against basic electrical safety and physics.
2. OVERVOLTAGE FLAG: If a document suggests connecting a component (e.g., 12V Fan) to a voltage significantly higher than its rating (e.g., 48V), you MUST flag this as a CRITICAL SAFETY HAZARD.
3. CONTRADICTIONS: If two documents contradict each other, highlight the discrepancy and recommend the safest path.
4. ZERO HALLUCINATION: Do not invent specs.

Provide a concise technical report."""
    
    prompt = f"Documentation found in Vault:\n{vault_context}\n\nUser Question: {test_query}"
    
    payload = {
        "model": "deepseek-r1:14b",
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    
    try:
        res = requests.post("http://127.0.0.1:11434/api/chat", json=payload, timeout=300).json()
        raw_content = res['message']['content']
        
        print("RAW ENGINEER OUTPUT:")
        print(raw_content)
        
        if "<think>" in raw_content:
            thinking = re.search(r'<think>(.*?)</think>', raw_content, re.DOTALL).group(1).strip()
            print("\n[ENGINEER'S INTERNAL THOUGHTS]:")
            print(thinking)
        
        # 3. PERSONA PASS (Hermes 3)
        print("\n" + "-" * 50)
        print("[STEP 3: PERSONA PASS (Hermes 3)]")
        
        persona_prompt = f"""You are JARVIS, Mark's senior engineering partner.
Translate the Engineer's Technical Synthesis into a peer-to-peer response for Mark.

STRICT RULE: If the Engineer flagged a safety hazard, YOU MUST emphasize it and warn Mark clearly. DO NOT smooth over the danger.

Engineer's Technical Synthesis:
{raw_content}

User Question: {test_query}"""

        final_response = llm_interface.query_llm(persona_prompt, model_override=llm_interface.RECEPTIONIST_MODEL)
        print(f"JARVIS FINAL RESPONSE:\n{final_response}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_system_2_test()
