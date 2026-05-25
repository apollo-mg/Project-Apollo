import json
import sys

def extract_text(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    transcript = []
    for turn in data:
        role = turn.get('role', 'unknown')
        parts = turn.get('parts', [])
        turn_text = []
        for part in parts:
            if 'text' in part:
                turn_text.append(part['text'])
            elif 'functionCall' in part:
                turn_text.append(f"[Function Call: {part['functionCall']['name']}]")
            elif 'functionResponse' in part:
                # Truncate long responses for the summary
                resp = str(part['functionResponse'].get('response', ''))
                if len(resp) > 200:
                    resp = resp[:200] + "..."
                turn_text.append(f"[Function Response: {resp}]")
        
        transcript.append(f"### {role.upper()}\n" + "\n".join(turn_text))
    
    return "\n\n".join(transcript)

if __name__ == "__main__":
    print(extract_text(sys.argv[1]))
