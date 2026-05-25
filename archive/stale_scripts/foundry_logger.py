import json
import os
import glob
from datetime import datetime

class FoundryLogger:
    def __init__(self, foundry_path="vault/foundry_logs.jsonl"):
        self.foundry_path = foundry_path
        os.makedirs(os.path.dirname(self.foundry_path), exist_ok=True)

    def log_turn(self, user_input, thought, actions, result, final_answer):
        """Logs a single interactive turn from Jarvis."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "source": "jarvis_live",
            "conversation": [
                {"role": "user", "content": user_input},
                {
                    "role": "assistant",
                    "thought": thought,
                    "actions": actions,
                    "tool_results": result,
                    "content": final_answer
                }
            ]
        }
        with open(self.foundry_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def ingest_gemini_cli(self, chats_dir):
        """Converts Gemini CLI session JSONs into Foundry format."""
        count = 0
        for chat_file in glob.glob(os.path.join(chats_dir, "session-*.json")):
            try:
                with open(chat_file, "r") as f:
                    data = json.load(f)
                
                # Extract turns
                messages = data.get("messages", [])
                
                for i in range(0, len(messages) - 1, 2):
                    user_msg = messages[i]
                    gemini_msg = messages[i+1]
                    
                    if user_msg["type"] == "user" and gemini_msg["type"] == "gemini":
                        turn = {
                            "timestamp": user_msg.get("timestamp"),
                            "source": "gemini_cli_ingest",
                            "conversation": [
                                {"role": "user", "content": self._extract_text(user_msg["content"])},
                                {
                                    "role": "assistant",
                                    "thought": gemini_msg.get("thoughts", []),
                                    "content": gemini_msg.get("content", "")
                                }
                            ]
                        }
                        with open(self.foundry_path, "a") as f:
                            f.write(json.dumps(turn) + "\n")
                        count += 1
            except Exception as e:
                print(f"Error ingesting {chat_file}: {e}")
        return count

    def _extract_text(self, content):
        if isinstance(content, str): return content
        if isinstance(content, list):
            return " ".join([c.get("text", "") for c in content if "text" in c])
        return str(content)

    def ingest_buddy_history(self, history_path):
        """Converts legacy buddy_history.json into Foundry format."""
        if not os.path.exists(history_path): return 0
        try:
            with open(history_path, "r") as f:
                history = json.load(f)
            
            count = 0
            for entry in history:
                turn = {
                    "timestamp": datetime.now().isoformat(),
                    "source": "buddy_history_legacy",
                    "conversation": [
                        {"role": "user", "content": entry.get("user")},
                        {"role": "assistant", "content": entry.get("buddy")}
                    ]
                }
                with open(self.foundry_path, "a") as f:
                    f.write(json.dumps(turn) + "\n")
                count += 1
            return count
        except Exception as e:
            print(f"Error ingesting history: {e}")
            return 0

if __name__ == "__main__":
    import sys
    logger = FoundryLogger()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--ingest-cli":
        cli_dir = os.path.expanduser("~/.gemini/tmp/gemini-infrastructure/chats")
        print(f"Ingesting Gemini CLI logs from {cli_dir}...")
        c = logger.ingest_gemini_cli(cli_dir)
        print(f"Done. Ingested {c} turns.")
        
    if len(sys.argv) > 1 and sys.argv[1] == "--ingest-history":
        print("Ingesting buddy_history.json...")
        c = logger.ingest_buddy_history("tmp/buddy_history.json")
        print(f"Done. Ingested {c} turns.")
