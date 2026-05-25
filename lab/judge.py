import os
import sys
import json
import glob
import agent_lens
from openai import OpenAI
from agent_lens import trace

# Install agent_lens auto-patching for OpenAI
agent_lens.install()

# Connect to the heavy model (e.g., P100 Node or local 9070)
API_URL = os.environ.get("OPENAI_BASE_URL", "http://10.0.0.71:8082/v1")
API_KEY = os.environ.get("OPENAI_API_KEY", "local-apollo-key")
MODEL_NAME = "Judge-Model" # Will use whatever is loaded on port 8082

client = OpenAI(base_url=API_URL, api_key=API_KEY)

JUDGE_SYSTEM_PROMPT = """You are an expert AI evaluator grading the performance of a local agent.
You will be provided with:
1. The Task Prompt given to the agent.
2. The Evaluation Criteria.
3. The Agent's Raw Output (including tool calls and stream events).

Your job is to read the output and determine if the agent successfully met the criteria.
You MUST output your evaluation in strict JSON format using this exact schema:
{
  "score": <int 1-5>,
  "passed": <boolean>,
  "reasoning": "<concise explanation of why it passed or failed>",
  "json_schema_broken": <boolean: true if the agent hallucinated XML or broken json>
}
"""

@trace
def call_llm(messages):
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.6,
            top_p=0.95,
            response_format={"type": "json_object"}
        )
        raw_content = response.choices[0].message.content
        
        try:
            # Strip markdown code blocks if the model wrapped the JSON
            clean_content = raw_content.strip()
            if clean_content.startswith("```json"):
                clean_content = clean_content[7:]
            elif clean_content.startswith("```"):
                clean_content = clean_content[3:]
            if clean_content.endswith("```"):
                clean_content = clean_content[:-3]
            
            return json.loads(clean_content.strip())
        except Exception as e:
            print(f"Error parsing JSON from judge output: {e}\\nRaw Output:\\n{raw_content}")
            return None
    except Exception as e:
        print(f"API Error: {e}")
        return None

def evaluate_run(file_path):
    print(f"\n⚖️  Evaluating Run: {os.path.basename(file_path)}")
    with open(file_path, "r") as f:
        results = json.load(f)
    
    evaluated_results = []
    
    for test in results:
        print(f"   Evaluating Test: {test['test_id']}...")
        
        user_prompt = f"""
TASK PROMPT:
{test['prompt']}

EVALUATION CRITERIA:
{test['eval_criteria']}

AGENT RAW OUTPUT:
{test['raw_output']}
"""
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        evaluation = call_llm(messages)
        
        if evaluation:
            test["evaluation"] = evaluation
            print(f"   -> Score: {evaluation.get('score')}/5 | Passed: {evaluation.get('passed')}")
        else:
            print("   -> ❌ Judge failed to return valid JSON.")
            
        evaluated_results.append(test)
        
    out_path = file_path.replace(".json", "_evaluated.json")
    with open(out_path, "w") as f:
        json.dump(evaluated_results, f, indent=2)
        
    print(f"\n💾 Evaluation complete. Saved to: {out_path}")

if __name__ == "__main__":
    results_dir = "/mnt/TG_2TB/Projects/Apollo/lab/results"
    
    # Find the most recent run file that hasn't been evaluated yet
    files = glob.glob(os.path.join(results_dir, "run_*.json"))
    files = [f for f in files if not f.endswith("_evaluated.json")]
    
    if not files:
        print("No unevaluated runs found in lab/results/")
        sys.exit(0)
        
    latest_run = max(files, key=os.path.getctime)
    evaluate_run(latest_run)