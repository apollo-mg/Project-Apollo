import json
import os
import sys
import re
from datetime import datetime
import llm_interface
import modules.sovereign_search as sovereign_search
from modules.theme import stylized_print, CLR_GOLD, CLR_CYAN, CLR_BLUE, CLR_RESET

# Simulation Configuration
SIM_MODEL = llm_interface.DEEP_ENGINEER_MODEL # DeepSeek-R1 14B
ACTORS = {
    "USA": "Focuses on 'America First' protectionism, decoupling from China, and maintaining naval dominance in the South China Sea.",
    "China": "Focuses on 'Reunification' narrative, breaking the first island chain, and establishing the Yuan as the reserve currency.",
    "Taiwan": "Focuses on 'Strategic Ambiguity' maintenance and high-tech semiconductor leverage (TSMC Shield).",
    "Apollo_Oracle": "The neutral, objective observer modeling game theory outcomes and black swan events."
}

class GeopoliticalSim:
    def __init__(self, target_date="March 31, 2026"):
        self.target_date = target_date
        self.history = []
        self.current_turn = 1
        self.grounding_data = ""

    def fetch_latest_grounding(self):
        """Uses Sovereign Search to ground the simulation in actual current events."""
        stylized_print("oracle", f"Grounding simulation in real-time data...", color=CLR_GOLD)
        queries = [
            "Current US China Taiwan tensions March 2026 summary"
        ]
        context = ""
        for q in queries:
            try:
                res = sovereign_search.sovereign_search(q)
                if "failed" in res.lower() or "error" in res.lower():
                    # Fallback to raw search snippets if synthesis fails
                    with sovereign_search.DDGS() as ddgs:
                        results = [r for r in ddgs.text(q, max_results=3)]
                        res = "\n".join([f"Title: {r['title']}\nSnippet: {r['body']}" for r in results])
                context += f"\n--- Grounding Data for '{q}' ---\n{res}\n"
            except Exception as e:
                context += f"\n--- Grounding Data for '{q}' failed: {e} ---\n"
        
        self.grounding_data = context
        print(f"\n{CLR_BLUE}[GROUNDING CONTEXT ACQUIRED]:{CLR_RESET}\n{self.grounding_data[:500]}...\n")

    def run_actor_turn(self, actor_name, description):
        """Simulates a specific actor's move using DeepSeek-R1."""
        stylized_print("engine", f"Simulating {actor_name} response...", color=CLR_CYAN)
        
        prompt = f"""### GEOPOLITICAL SIMULATION: THE MARCH 31 TURN
CURRENT DATE IN SIM: {datetime.now().strftime('%B %d, %Y')}
TARGET EVENT: Xi-Trump Summit / March 31 Deadline
ACTOR: {actor_name}
ACTOR PHILOSOPHY: {description}

REAL-WORLD GROUNDING DATA:
{self.grounding_data}

PREVIOUS MOVES:
{json.dumps(self.history[-5:], indent=2) if self.history else "No previous moves."}

TASK:
1. Analyze the current state of play.
2. Formulate {actor_name}'s next strategic move.
3. Predict the immediate secondary impact on global markets and security.

Provide your response in raw text (no markdown) focused on cold, hard strategic logic.
"""
        
        response = llm_interface.query_llm(prompt, model_override=SIM_MODEL)
        # Extract content from <think> if present, but for the history we want the result
        clean_res = response.split("</think>")[-1].strip()
        
        move = {
            "turn": self.current_turn,
            "actor": actor_name,
            "timestamp": datetime.now().isoformat(),
            "move_logic": clean_res
        }
        self.history.append(move)
        return clean_res

    def generate_sitrep(self):
        """Uses the 35B Architect to synthesize the 14B's raw moves into a high-density SITREP."""
        stylized_print("architect", "Synthesizing Final SITREP...", color=CLR_BLUE)
        
        history_text = ""
        for m in self.history:
            history_text += f"[{m['actor']} Turn {m['turn']}]: {m['move_logic']}\n\n"
            
        prompt = f"""You are the Apollo Architect. You have monitored a 4-actor geopolitical simulation regarding the March 31 Turn.
Analyze the raw moves provided and synthesize a high-density Strategic Situation Report (SITREP).

RAW SIMULATION DATA:
{history_text}

SITREP REQUIREMENTS:
1. Identify the 'Center of Gravity' for the upcoming March 31 event.
2. Quantify the probability of: [Ceasefire, Decoupling, Kinetic Conflict].
3. Detail the 'Alpha Move' for Mark (the Sovereign User) to protect assets or leverage opportunities.

FORMAT: Use professional, high-signal military/intelligence briefing style.
"""
        sitrep = llm_interface.query_llm(prompt, model_override=llm_interface.ARCHITECT_MODEL)
        
        # Auto-save results
        sim_data = {
            "timestamp": datetime.now().isoformat(),
            "history": self.history,
            "sitrep": sitrep
        }
        save_path = f"geopolitical_sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(save_path, 'w') as f:
            json.dump(sim_data, f, indent=4)
        stylized_print("system", f"Simulation results saved to {save_path}", color=CLR_GOLD)
        
        return sitrep

    def run_simulation(self):
        print(f"\n{CLR_GOLD}=== INITIALIZING MARCH 31 GAME THEORY SIMULATION ==={CLR_RESET}\n")
        
        self.fetch_latest_grounding()
        
        for actor, desc in ACTORS.items():
            move = self.run_actor_turn(actor, desc)
            print(f"\n{CLR_CYAN}[{actor} MOVE]:{CLR_RESET}\n{move}\n")
            print("-" * 60)
            
        sitrep = self.generate_sitrep()
        
        print(f"\n{CLR_GOLD}========================================================{CLR_RESET}")
        print(f"{CLR_GOLD}                FINAL STRATEGIC SITREP{CLR_RESET}")
        print(f"{CLR_GOLD}========================================================{CLR_RESET}\n")
        print(sitrep)
        print(f"\n{CLR_GOLD}========================================================{CLR_RESET}\n")

if __name__ == "__main__":
    sim = GeopoliticalSim()
    sim.run_simulation()
