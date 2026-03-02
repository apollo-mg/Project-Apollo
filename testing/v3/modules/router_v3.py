import llm_interface_v3 as llm_interface
import json
import re

def classify_intent(user_input):
    """
    Cascading Router:
    Stage 1: Qwen 0.5B (Gatekeeper) handles fast, simple triage (SYSTEM, SHOP, CHITCHAT).
    Stage 2: If Gatekeeper struggles or assigns complex work (DEV, ARCHITECT, DEEP_THINK), it escalates to Qwen3 8B (Thinker).
    """
    
    stage_1_prompt = """You are the Apollo Dispatcher (Stage 1). Your job is to route user requests.

CRITICAL: Return ONLY a raw JSON object. NO markdown. NO preamble. NO conversational text.

MODULES:
- 'SHOP': 3D printing, hardware, visual analysis, image identification.
- 'SYSTEM': Hardware stats, VRAM, power, status.
- 'CHITCHAT': Greetings, simple talk.
- 'COMPLEX': Any request involving coding, Python, scripts, bug fixing, refactoring, architecture, deep logic, or race conditions. (ESCALATE)

EXAMPLES:
User: "How much VRAM am I using?"
{"module": "SYSTEM", "priority": "P2", "reason": "system query"}

User: "Scan this PCB."
{"module": "SHOP", "priority": "P1", "reason": "visual hardware analysis"}

User: "Write a python script to parse a csv file."
{"module": "COMPLEX", "priority": "P2", "reason": "escalate coding task"}

User: "Debug this race condition."
{"module": "COMPLEX", "priority": "P1", "reason": "escalate reasoning task"}

User: "I need a complete architectural refactor of the Vault."
{"module": "COMPLEX", "priority": "P1", "reason": "escalate architecture task"}
"""

    stage_2_prompt = """You are the Apollo Dispatcher (Stage 2 - Thinker). Your job is to route COMPLEX user requests.

CRITICAL: Return ONLY a raw JSON object. NO markdown. NO preamble. NO conversational text.

MODULES:
- 'DEV': Primary coding, fast scripts, python/bash.
- 'DEEP_THINK': Complex reasoning, bug root-cause analysis, Chain-of-Thought (DeepSeek-R1).
- 'ARCHITECT': Complex structural logic, large context refactoring, CAD.
- 'RESEARCH': General knowledge, web searches, data analysis.

EXAMPLES:
User: "Write a script."
{"module": "DEV", "priority": "P2", "reason": "coding task"}

User: "Debug this race condition."
{"module": "DEEP_THINK", "priority": "P1", "reason": "complex reasoning"}

User: "Refactor the Vault architecture."
{"module": "ARCHITECT", "priority": "P1", "reason": "structural change"}
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
        # STAGE 1: Fast Triage (Gatekeeper)
        print(f"--- [ROUTER: Stage 1 Gatekeeper ({llm_interface.GATEKEEPER_MODEL})] ---")
        stage_1_response = llm_interface.query_llm(
            prompt=user_input, 
            system_message=stage_1_prompt, 
            model_override=llm_interface.GATEKEEPER_MODEL
        )
        
        data_s1 = parse_json(stage_1_response)
        
        # If parsing failed, or it's flagged as COMPLEX, escalate.
        if not data_s1 or data_s1.get("module") == "COMPLEX":
            print(f"--- [ROUTER: Stage 2 Escalation ({llm_interface.ENGINEER_MODEL})] ---")
            stage_2_response = llm_interface.query_llm(
                prompt=user_input, 
                system_message=stage_2_prompt, 
                model_override=llm_interface.ENGINEER_MODEL
            )
            data_s2 = parse_json(stage_2_response)
            
            if data_s2:
                data_s2["routed_by"] = "Stage 2 (Thinker)"
                return data_s2
            return {"module": "CHITCHAT", "priority": "P3", "reason": "Stage 2 Parsing failed", "routed_by": "Fallback"}

        data_s1["routed_by"] = "Stage 1 (Gatekeeper)"
        return data_s1

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
