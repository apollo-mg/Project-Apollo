import llm_interface
import json
import re

def classify_intent(user_input):
    """
    Cascading Router (System 1.5 Architecture):
    Stage 1: Qwen3 0.6B (Gatekeeper) - Fast triage (CHITCHAT, SYSTEM, SHOP).
    Stage 2: Qwen3 8B (Thinker) - General engineering, coding, and research (DEV, RESEARCH).
    Stage 3: Qwen3-Coder 30B (Architect) - Complex structural logic, CAD, and deep reasoning (ARCHITECT, DEEP_THINK).
    """
    
    stage_1_prompt = """You are the Apollo Dispatcher (Stage 1). Your job is to route user requests.

CRITICAL: Return ONLY a raw JSON object. NO markdown. NO preamble. NO conversational text.

MODULES:
- 'SHOP': 3D printing, hardware, visual analysis, image identification.
- 'SYSTEM': Hardware stats, VRAM, power, status.
- 'CHITCHAT': Greetings, simple talk, non-tasks.
- 'ESCALATE': Any request involving coding, logic, research, architecture, or complex reasoning.

EXAMPLES:
User: "Hi Zoey!"
{"module": "CHITCHAT", "priority": "P3", "reason": "greeting"}

User: "How much VRAM am I using?"
{"module": "SYSTEM", "priority": "P2", "reason": "system query"}

User: "Scan this PCB."
{"module": "SHOP", "priority": "P1", "reason": "visual hardware analysis"}

User: "Write a script."
{"module": "ESCALATE", "priority": "P2", "reason": "coding task"}
"""

    stage_2_prompt = """You are the Apollo Dispatcher (Stage 2 - Thinker). Your job is to route user requests.

CRITICAL: Return ONLY a raw JSON object. NO markdown. NO preamble. NO conversational text.

MODULES:
- 'DEV': Standard coding, fast scripts, python/bash.
- 'RESEARCH': General knowledge, web searches, data analysis.
- 'ESCALATE': Complex structural logic, CAD, deep bug analysis, or large context refactoring.

EXAMPLES:
User: "Write a python script to parse a csv file."
{"module": "DEV", "priority": "P2", "reason": "coding task"}

User: "What is the melting point of PLA?"
{"module": "RESEARCH", "priority": "P3", "reason": "general knowledge"}

User: "Refactor the Vault architecture."
{"module": "ESCALATE", "priority": "P1", "reason": "architectural task"}
"""

    stage_3_prompt = """You are the Apollo Dispatcher (Stage 3 - Architect). Your job is to route the most COMPLEX requests.

CRITICAL: Return ONLY a raw JSON object. NO markdown. NO preamble. NO conversational text.

MODULES:
- 'ARCHITECT': Complex structural logic, CAD (FeatureScript), large-scale refactoring.
- 'DEEP_THINK': Complex reasoning, bug root-cause analysis, Chain-of-Thought (DeepSeek-R1).
"""

    def parse_json(response_text):
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if "module" in data:
                    data["module"] = data["module"].upper()
                else:
                    data["module"] = "CHITCHAT"
                return data
            except json.JSONDecodeError:
                pass
        return None

    try:
        # STAGE 1: Gatekeeper (0.6B)
        print(f"--- [ROUTER: Stage 1 Gatekeeper ({llm_interface.GATEKEEPER_MODEL})] ---")
        s1_res = llm_interface.query_llm(user_input, system_message=stage_1_prompt, model_override=llm_interface.GATEKEEPER_MODEL)
        data = parse_json(s1_res)
        
        if not data or data.get("module") == "ESCALATE":
            # STAGE 2: Thinker (8B)
            print(f"--- [ROUTER: Stage 2 Thinker ({llm_interface.ENGINEER_MODEL})] ---")
            s2_res = llm_interface.query_llm(user_input, system_message=stage_2_prompt, model_override=llm_interface.ENGINEER_MODEL)
            data = parse_json(s2_res)
            
            if not data or data.get("module") == "ESCALATE":
                # STAGE 3: Architect (30B)
                print(f"--- [ROUTER: Stage 3 Architect ({llm_interface.ARCHITECT_MODEL})] ---")
                s3_res = llm_interface.query_llm(user_input, system_message=stage_3_prompt, model_override=llm_interface.ARCHITECT_MODEL)
                data = parse_json(s3_res)
                if data: data["routed_by"] = "Stage 3 (Architect)"
            else:
                data["routed_by"] = "Stage 2 (Thinker)"
        else:
            data["routed_by"] = "Stage 1 (Gatekeeper)"

        return data or {"module": "CHITCHAT", "priority": "P3", "reason": "Routing failed", "routed_by": "Fallback"}

    except Exception as e:
        return {"module": "CHITCHAT", "priority": "P3", "reason": f"Router Error: {e}", "routed_by": "Error"}


    except Exception as e:
        return {"module": "CHITCHAT", "priority": "P3", "reason": f"Router Error: {e}", "routed_by": "Error"}

def get_module_prompt(module_name):
    """Returns specialized context for the routed module."""
    prompts = {
        "SHOP": "You are currently in SHOP mode. ZERO-TRUST INVENTORY: If an item is NOT explicitly listed in the CURRENT INVENTORY context, it is MISSING. Do not assume or hallucinate entries.",
        "DEV": "You are currently in DEV mode. Use Qwen3-8B for fast, accurate coding. If a problem is too complex, flag for DEEP_THINK.",
        "DEEP_THINK": "You are the Reasoning Specialist (DeepSeek-R1). You use internal Chain-of-Thought (<think> tags) to decompose and solve the most difficult engineering problems.",
        "ARCHITECT": "You are the ARCHITECT (Qwen3-Coder 30B). You handle complex structural logic, parametric CAD design (FeatureScript/OpenSCAD), and large-scale refactoring. Think deeply about the system as a whole.",
        "RESEARCH": "You are currently in RESEARCH mode. Focus on verified facts and deep analysis.",
        "SYSTEM": "You are currently in SYSTEM mode. Focus on hardware stats and resource efficiency.",
        "LIBRARIAN": "You are currently in LIBRARIAN mode. Focus on knowledge ingestion, technical documentation, and organizing The Vault."
    }
    return prompts.get(module_name, "You are Zoey, a helpful assistant.")
