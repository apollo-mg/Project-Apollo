import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import re
import llm_interface

def fetch_url_content(url):
    """Fetches and extracts clean text from a webpage."""
    print(f"    [Scraping] {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Kill javascript and CSS
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        # Condense whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Return first 1500 chars to avoid blowing up the context window
        return text[:1500]
    except Exception as e:
        return f"Error fetching URL: {e}"

def perform_search(query, num_results=3):
    """Uses DuckDuckGo to find relevant links, then scrapes them."""
    print(f"\n[*] Executing Web Search: '{query}'")
    results_data = []
    
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=num_results)]
            
            for r in results:
                url = r.get('href')
                snippet = r.get('body')
                title = r.get('title')
                
                content = fetch_url_content(url)
                
                results_data.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "scraped_content": content
                })
    except Exception as e:
        print(f"[-] Search failed: {e}")
            
    return results_data

def synthesize_answer(query, search_results):
    """Feeds the scraped web data to the Architect to synthesize a Google-like answer."""
    print(f"\n[*] Synthesizing data with Unified Model...")
    
    context = ""
    for idx, r in enumerate(search_results):
        context += f"\n--- Source [{idx+1}]: {r['title']} ---\n"
        context += f"URL: {r['url']}\n"
        context += f"Content: {r['scraped_content']}\n"

    prompt = f"""You are the Sovereign Research AI. Answer the user's query using ONLY the provided web search context.
Cite your sources using brackets (e.g. [1]). Do not hallucinate information outside of the context.

User Query: {query}

Web Context:
{context}
"""
    
    try:
        final_answer = llm_interface.query_llm(prompt)
        return final_answer
    except Exception as e:
        return f"[-] Synthesis failed: {e}"

def sovereign_search(query):
    """The master search loop."""
    raw_data = perform_search(query)
    if not raw_data:
        return "No results found."
        
    answer = synthesize_answer(query, raw_data)
    
    # Format the return string to look exactly like the console output
    output = []
    output.append("========================================================")
    output.append("                 SOVEREIGN SEARCH RESULT")
    output.append("========================================================\n")
    output.append(answer)
    output.append("\n--------------------------------------------------------")
    output.append("Sources:")
    for idx, r in enumerate(raw_data):
        output.append(f"[{idx+1}] {r['url']}")
    output.append("========================================================\n")
    
    result_str = "\n".join(output)
    return result_str

if __name__ == "__main__":
    test_query = "What were the major changes in the latest Linux kernel release?"
    print(sovereign_search(test_query))
