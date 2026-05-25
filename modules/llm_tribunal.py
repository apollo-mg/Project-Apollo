#!/usr/bin/env python3
import json
import urllib.request
import urllib.error

def evaluate_and_rank_epiphanies(input_file="deduplicated_epiphanies.jsonl", output_file="ranked_queue.json"):
    print(f"[*] Reading epiphanies from {input_file}...")
    epiphanies = []
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    epiphanies.append(json.loads(line))
    except FileNotFoundError:
        print(f"[!] Error: {input_file} not found.")
        return
        
    print(f"[*] Found {len(epiphanies)} epiphanies to evaluate.")
    
    url = "http://127.0.0.1:8082/v1/chat/completions"
    system_prompt = (
        "You are a Senior Staff Engineer evaluating a proposed architectural change. "
        "Score the following proposal strictly on these metrics. "
        "You must respond ONLY with a valid JSON object matching the following schema exactly:\n"
        "{\n"
        '  "feasibility_score": <integer 1-10, can a single agent realistically implement this without breaking the codebase?>,\n'
        '  "impact_score": <integer 1-10, how much value does this add?>,\n'
        '  "risk_level": <string "Low", "Medium", "High", "Extreme">,\n'
        '  "is_actionable": <boolean>\n'
        "}"
    )
    
    evaluated_epiphanies = []
    
    for i, item in enumerate(epiphanies, 1):
        print(f"\n[*] Evaluating [{i}/{len(epiphanies)}]: {item.get('epiphany', '')[:60]}...")
        
        epiphany_text = item.get("epiphany", "No epiphany text provided.")
        reasoning_text = item.get("reasoning", "No reasoning provided.")
        
        user_prompt = f"Epiphany:\n{epiphany_text}\n\nReasoning:\n{reasoning_text}"
        
        payload = {
            "model": "Qwopus-27B",
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result['choices'][0]['message']['content']
                
                # Parse the JSON response strictly
                try:
                    evaluation = json.loads(content)
                except json.JSONDecodeError:
                    print(f"  [!] Warning: Could not parse JSON from model response. Skipping.")
                    print(f"  [!] Raw content: {content}")
                    continue
                
                # Extract fields with safe defaults
                feasibility_score = int(evaluation.get("feasibility_score", 0))
                impact_score = int(evaluation.get("impact_score", 0))
                risk_level = str(evaluation.get("risk_level", "Extreme"))
                is_actionable = bool(evaluation.get("is_actionable", False))
                
                # Calculate final score based on ranking logic
                final_score = 0.0
                if not is_actionable or risk_level.lower() == "extreme":
                    print("  [-] Item dropped/scored 0 (Not actionable or Extreme risk).")
                else:
                    final_score = (feasibility_score * 1.5) + impact_score
                
                # Update the original object with evaluation details
                item["llm_evaluation"] = evaluation
                item["final_score"] = final_score
                
                evaluated_epiphanies.append(item)
                print(f"  [+] Final Score: {final_score} (Feasibility: {feasibility_score}, Impact: {impact_score}, Risk: {risk_level})")
                
        except urllib.error.URLError as e:
            print(f"  [!] Error communicating with LLM server: {e}")
            continue
        except Exception as e:
            print(f"  [!] Unexpected error during evaluation: {e}")
            continue
            
    # Sort the list descending by final_score
    print("\n[*] Sorting evaluated epiphanies by final score...")
    evaluated_epiphanies.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    
    # Write to the final output file as a single JSON array
    print(f"[*] Writing {len(evaluated_epiphanies)} ranked epiphanies to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(evaluated_epiphanies, f, indent=4)
        
    print("[*] Tribunal Ranking complete!")

if __name__ == "__main__":
    evaluate_and_rank_epiphanies()
