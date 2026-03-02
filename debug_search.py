from duckduckgo_search import DDGS
from googlesearch import search
import requests

print("--- TESTING DDGS ---")
try:
    with DDGS() as ddgs:
        res = list(ddgs.text("EBB36 manual", max_results=3))
        print(f"DDGS Results: {len(res)}")
        for r in res: print(r['href'])
except Exception as e: print(f"DDGS Error: {e}")

print("\n--- TESTING GOOGLESEARCH ---")
try:
    res = list(search("EBB36 manual", num_results=3, advanced=True))
    print(f"Google Results: {len(res)}")
    for r in res: print(r.url)
except Exception as e: print(f"Google Error: {e}")

print("\n--- TESTING REQUESTS ---")
try:
    resp = requests.get("https://www.google.com")
    print(f"Google HTTP Status: {resp.status_code}")
except Exception as e: print(f"HTTP Error: {e}")
