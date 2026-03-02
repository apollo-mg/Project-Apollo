import os
import json
import time
from modules.core import load_json, save_json

INVENTORY_PATH = "vault/inventory.json"

def load_inventory():
    if not os.path.exists(INVENTORY_PATH):
        # Initial template
        return {
            "last_updated": time.time(),
            "items": [],
            "categories": {
                "GPU": [],
                "CPU": [],
                "RAM": [],
                "STORAGE": [],
                "NETWORKING": [],
                "MISC": []
            }
        }
    return load_json(INVENTORY_PATH)

def add_hardware(name, category, specs=None, quantity=1, status="in_stock", force=False):
    """Adds or updates hardware in the inventory with de-duplication safety."""
    inventory = load_inventory()
    
    # Strict matching
    existing_item = None
    for item in inventory["items"]:
        if item["name"].lower() == name.lower():
            existing_item = item
            break
            
    if existing_item and not force:
        return f"AUDIT ALERT: '{name}' already exists (Qty: {existing_item['quantity']}). Use 'force=True' or a specific quantity update to change it."

    if existing_item and force:
        existing_item["quantity"] = quantity
        existing_item["last_seen"] = time.time()
        existing_item["specs"].update(specs or {})
        res_msg = f"Inventory UPDATED: {name} (Set to Qty: {quantity})"
    else:
        new_item = {
            "name": name,
            "category": category.upper(),
            "specs": specs or {},
            "quantity": quantity,
            "status": status,
            "added_at": time.time(),
            "last_seen": time.time(),
            "est_value_usd": 0,
            "forensic_signatures": []
        }
        inventory["items"].append(new_item)
        if category.upper() not in inventory["categories"]:
            inventory["categories"][category.upper()] = []
        if name not in inventory["categories"][category.upper()]:
            inventory["categories"][category.upper()].append(name)
        res_msg = f"Inventory NEW ITEM: {name} (Qty: {quantity})"

    inventory["last_updated"] = time.time()
    save_json(INVENTORY_PATH, inventory)
    return res_msg

def get_inventory_summary():
    inventory = load_inventory()
    summary = ["--- 📦 SHOP INVENTORY SUMMARY ---"]
    for cat, items in inventory["categories"].items():
        if items:
            summary.append(f"{cat}: {len(items)} unique types")
    return "\n".join(summary)

def diff_inventory(items_to_check):
    """
    Programmatically compares a list of item names against the inventory.
    Returns a JSON string of 'present' and 'missing' items.
    """
    inventory = load_inventory()
    present = []
    missing = []
    
    # Simple lower-case exact substring matching for safety
    inventory_names = [item["name"].lower() for item in inventory["items"]]
    
    for item in items_to_check:
        found = False
        for inv_name in inventory_names:
            if item.lower() in inv_name or inv_name in item.lower():
                found = True
                break
        if found:
            present.append(item)
        else:
            missing.append(item)
            
    return json.dumps({"present": present, "missing": missing}, indent=2)

def search_inventory(query):
    inventory = load_inventory()
    results = []
    q = query.lower()
    for item in inventory["items"]:
        if q in item["name"].lower() or q in item["category"].lower():
            results.append(f"- {item['name']} (Qty: {item['quantity']}) | {item['status']}")
    return "\n".join(results) if results else "No matching items found."

def update_item_status(name, status):
    """Updates the status of an item (e.g., 'damaged', 'broken', 'in_use')."""
    inventory = load_inventory()
    for item in inventory["items"]:
        if item["name"].lower() == name.lower():
            item["status"] = status
            item["last_updated"] = time.time()
            save_json(INVENTORY_PATH, inventory)
            return f"Status for '{item['name']}' updated to: {status}"
    return f"Item '{name}' not found in inventory."

def add_to_wishlist(name, category, notes=""):
    """Adds an item to a wishlist file."""
    wishlist_path = "vault/wishlist.json"
    wishlist = []
    if os.path.exists(wishlist_path):
        wishlist = load_json(wishlist_path)
    
    wishlist.append({
        "name": name,
        "category": category.upper(),
        "notes": notes,
        "added_at": time.time()
    })
    save_json(wishlist_path, wishlist)
    return f"Added to Wishlist: {name} ({category})"
