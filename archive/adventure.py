import sys
import json
import os
import time
from modules.theme import stylized_print, CLR_CYAN, CLR_GOLD, CLR_RESET
import llm_interface

UI_STATE_FILE = "data/ui_state.json"

# The "World Bible" for the LLM
SYSTEM_PROMPT = """You are the AI Dungeon Master for a hard sci-fi text adventure.
The player is the lone surviving engineer on the "USG Ishimura", a deep-space mining vessel that has suffered a catastrophic systems failure.
Atmosphere is tense, industrial, and gritty (think Dead Space, Alien, or The Expanse).

RULES:
1. Progress the story logically based on the user's input.
2. The user has finite health (max 100) and oxygen (max 100).
3. Actions have consequences.
4. Keep the narrative prose concise (2-3 paragraphs max).

CRITICAL REQUIREMENT:
You MUST output your response in valid JSON format matching this exact schema:
{
  "narrative": "The descriptive text of what happens...",
  "state": {
    "location": "Engineering Bay",
    "health": 90,
    "oxygen": 85,
    "alert_level": "WARNING" // Can be "NORMAL", "WARNING", or "CRITICAL"
  }
}
Do NOT wrap the JSON in markdown code blocks. Output ONLY the raw JSON.
"""

class SovereignAdventure:
    def __init__(self):
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.current_state = {
            "location": "Cryo-Sleep Chamber",
            "health": 100,
            "oxygen": 100,
            "alert_level": "CRITICAL"
        }
        
    def update_dradis_ui(self):
        """Pushes the current game state to the Planar screen via dynamic_canvas.py"""
        
        # Determine radar color based on alert level
        radar_color = "#FFB000" # Default Amber
        if self.current_state.get("alert_level") == "CRITICAL":
            radar_color = "#FF0000" # Red
        elif self.current_state.get("alert_level") == "NORMAL":
            radar_color = "#00FF00" # Green
            
        payload = {
            "root": {
                "type": "VBox",
                "children": [
                    {
                        "type": "Label",
                        "text": f"LOCATION: {self.current_state.get('location', 'UNKNOWN')}",
                        "style": {"font": ["bold"]}
                    },
                    {
                        "type": "HBox",
                        "children": [
                            {"type": "Label", "text": f"VITALS: {self.current_state.get('health', 0)}%"},
                            {"type": "Label", "text": f"O2 LEVEL: {self.current_state.get('oxygen', 0)}%"}
                        ]
                    },
                    {
                        "type": "Label",
                        "text": f"STATUS: {self.current_state.get('alert_level', 'UNKNOWN')}",
                        "style": {"font": ["bold"]}
                    }
                ]
            }
        }
        
        # Write to the file that dynamic_canvas.py is polling
        try:
            with open(UI_STATE_FILE, 'w') as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            print(f"UI Sync Error: {e}")

    def run(self):
        stylized_print("engine", "Initializing Sovereign Adventure Engine...", color=CLR_CYAN)
        self.update_dradis_ui()
        
        print(f"\n{CLR_GOLD}You wake up. The cryo-pod hisses open. The emergency lights are spinning.{CLR_RESET}")
        print(f"{CLR_GOLD}The ship is violently shuddering. What do you do?{CLR_RESET}\n")
        
        while True:
            try:
                user_input = input(f"\n> ")
                if user_input.lower() in ['quit', 'exit']:
                    print("Saving state... Goodbye, Engineer.")
                    break
                    
                self.history.append({"role": "user", "content": user_input})
                
                # Query the 35B model
                print(f"{CLR_CYAN}[Processing World State...]{CLR_RESET}")
                raw_response = llm_interface.query_llm_messages(self.history, model_override=llm_interface.ARCHITECT_MODEL)
                
                # Parse the JSON
                try:
                    # Strip any accidental markdown formatting the LLM might have added
                    clean_json = raw_response.strip().replace('```json', '').replace('```', '').strip()
                    response_data = json.loads(clean_json)
                    
                    narrative = response_data.get("narrative", "Error rendering narrative.")
                    new_state = response_data.get("state", self.current_state)
                    
                    self.current_state = new_state
                    self.history.append({"role": "assistant", "content": clean_json})
                    
                    # Update the Planar Screen
                    self.update_dradis_ui()
                    
                    # Print the story to the terminal
                    print(f"\n{narrative}\n")
                    
                except json.JSONDecodeError:
                    print(f"{CLR_GOLD}[SYSTEM ERROR: The DM hallucinated an invalid state. Raw output below:]{CLR_RESET}")
                    print(raw_response)
                    self.history.pop() # Remove the failed turn
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break

if __name__ == "__main__":
    game = SovereignAdventure()
    game.run()
