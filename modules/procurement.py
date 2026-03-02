import os
import json
import time
from modules.core import load_json, save_json
import llm_interface

PRICE_BOOK_PATH = "vault/price_book.json"

def load_price_book():
    if not os.path.exists(PRICE_BOOK_PATH):
        return {"items": {}}
    return load_json(PRICE_BOOK_PATH)

def analyze_flyer(text_content):
    """
    Analyzes flyer text against the price book to find deals using the LLM.
    Returns a list of deal alerts.
    """
    price_book = load_price_book()

    prompt = f"""
You are a Deal Hunter. Analyze the following ad text against the provided price book.
Identify any items from the price book that are mentioned in the ad.
Determine if the advertised price is a 'good deal' (e.g., lower than standard price or close to the lowest seen price).
Return your findings as a concise list of deals or 'No notable deals found.'

PRICE BOOK:
{json.dumps(price_book, indent=2)}

AD TEXT:
{text_content}
"""
    try:
        response = llm_interface.query_llm(prompt, model_override=llm_interface.ENGINEER_MODEL)
        return response
    except Exception as e:
        return f"Error analyzing flyer: {e}"

def update_price(item_name, new_price, store_name="Unknown"):
    """
    Updates the lowest seen price if the new price is lower.
    """
    book = load_price_book()
    item_key = item_name.lower()
    
    if item_key in book.get("items", {}):
        item = book["items"][item_key]
        if new_price < item.get("lowest_seen_price", float('inf')):
            item["lowest_seen_price"] = new_price
            item["last_updated"] = time.time()
            item["lowest_seen_store"] = store_name
            save_json(PRICE_BOOK_PATH, book)
            return f"Updated {item_name}: New lowest price is ${new_price} at {store_name}."
        return f"{item_name} at ${new_price} is not lower than the historical lowest (${item.get('lowest_seen_price')})."
    else:
        return f"Item '{item_name}' not found in the price book."
