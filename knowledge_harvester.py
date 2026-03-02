import requests
import os
import re
import shutil

MIN_FREE_SPACE_GB = 5  # Stop if free space drops below this

def learn_topic(topic):
    print(f"--- [KNOWLEDGE HARVESTER] Learning: {topic} ---")
    
    try:
        # 0. Safety Check: Disk Space
        vault_root = "vault"
        if not os.path.exists(vault_root): os.makedirs(vault_root, exist_ok=True)
        
        total, used, free = shutil.disk_usage(vault_root)
        free_gb = free / (2**30)
        
        if free_gb < MIN_FREE_SPACE_GB:
            return f"SAFETY LOCK: Insufficient disk space ({free_gb:.2f} GB free). Minimum {MIN_FREE_SPACE_GB} GB required to continue harvesting."

        # 1. Search (Opensearch)
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action": "opensearch",
            "search": topic,
            "limit": 1,
            "namespace": 0,
            "format": "json"
        }
        
        # User-Agent is required by Wiki API policies
        headers = {'User-Agent': 'Jarvis/1.0 (Gemini Infrastructure; mail@example.com)'}
        
        res = requests.get(search_url, params=search_params, headers=headers)
        data = res.json()
        
        if not data[1]:
            return f"No Wikipedia results found for '{topic}'."
            
        best_title = data[1][0]
        best_url = data[3][0]
        print(f"Match found: {best_title}")
        
        # 2. Get Content (Extract)
        # We use 'query' with 'extracts' prop for plain text
        content_params = {
            "action": "query",
            "format": "json",
            "titles": best_title,
            "prop": "extracts",
            "explaintext": True, # Returns plain text
            "exsectionformat": "wiki" # Tries to keep structure
        }
        
        res = requests.get(search_url, params=content_params, headers=headers)
        data = res.json()
        
        pages = data["query"]["pages"]
        page_id = list(pages.keys())[0]
        content = pages[page_id].get("extract", "")
        
        if not content:
            return "Failed to extract content."

        # 3. Clean and Format (Markdown)
        # Wiki extracts usually come as plain text but headers might be formatted differently or missing formatting.
        # 'explaintext' gives decent results but '== Section ==' structure is preserved often.
        
        clean_content = re.sub(r'===(.*?)===', r'### \1', content)
        clean_content = re.sub(r'==(.*?)==', r'## \1', clean_content)
        
        markdown_out = f"# {best_title}\n\n"
        markdown_out += f"**Source:** {best_url}\n\n"
        markdown_out += "---\n\n"
        markdown_out += clean_content
        
        # 4. Save to Vault
        filename = f"{best_title.replace(' ', '_')}.md"
        filename = re.sub(r'[^\w\-_.]', '', filename) # Sanitize
        
        # Save to vault/knowledge
        # Check if pilot_ingest supports .md files? We need to verify.
        # If not, we might need to rely on the Grep Fallback or update ingestion.
        save_dir = "vault/knowledge"
        os.makedirs(save_dir, exist_ok=True)
        
        save_path = os.path.join(save_dir, filename)
        with open(save_path, "w") as f:
            f.write(markdown_out)
            
        print(f"Saved to: {save_path} ({len(content)} chars)")
        
        # 5. Indexing Advice
        # We need to ensure the ingestion script picks this up.
        # buddy_agent.Toolbox.scan_vault() triggers pilot_ingest.py.
        # Let's verify pilot_ingest.py behavior separately.
        
        return f"Successfully learned '{best_title}'. Saved to {save_path}. (Ready for indexing)"

    except Exception as e:
        return f"Harvest Error: {e}"

if __name__ == "__main__":
    # Test run
    print(learn_topic("Radio frequency"))
