import json

def get_shop_inventory():
    return {
        "items": [
            {"name": "Drill Bits", "quantity": 12},
            {"name": "Screwdrivers", "quantity": 8},
            {"name": "Orange Pliers", "quantity": 1},
            {"name": "Wrenches", "quantity": 12},
            {"name": "LED Flashlight", "quantity": 1}
        ]
    }

# Save inventory to a JSON file
inventory_data = get_shop_inventory()
with open('shop_inventory.json', 'w') as f:
    json.dump(inventory_data, f, indent=2)