import sys
import argparse
from llm_interface import query_llm

def delegate_task(instruction):
    """
    Sends a task to the local Qwen 35B MoE and returns the raw output.
    This acts as the bridge for the Architect (Gemini CLI) to offload work.
    """
    system_prompt = "You are Zoey, a highly capable local AI running on an RX 9070 XT. Fulfill the following technical request accurately and without conversational filler. Provide only the requested code or architecture."
    
    response = query_llm(instruction, system_message=system_prompt)
    print(response)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Foundry Delegation Bridge")
    parser.add_argument("task", help="The technical task to delegate to Zoey.")
    args = parser.parse_args()
    
    delegate_task(args.task)
