import requests
import sys

# Using port 8001 based on our current server state
API_URL = "http://localhost:8001"

def seed_demo():
    print("🌱 Seeding 'The Souled Stole' demo state...")
    
    try:
        res = requests.get(f"{API_URL}/")
        if res.status_code != 200:
            raise Exception
    except:
        print("❌ Error: FastAPI server is not running on port 8001. Please start it first.")
        sys.exit(1)

    payload = {
        "principal": "Demo Judge",
        "limits": {
            "max_per_transaction": 3000.0,
            "max_total_spend_today": 5000.0,
            "allowed_categories": ["apparel", "accessories"],
            "auto_approve_below": 2000.0,
            "max_discount_agent_can_accept_pct": 15.0
        }
    }
    
    print("⏳ Generating signed Spend Mandate...")
    res = requests.post(f"{API_URL}/api/mandate", json=payload)
    data = res.json()
    
    if "mandate_id" in data:
        print(f"✅ Demo Mandate Created Successfully!")
        print(f"   Mandate ID: {data['mandate_id']}")
        print(f"   Auto-Approve Limit: ₹{payload['limits']['auto_approve_below']}")
        print(f"   Absolute Max Limit: ₹{payload['limits']['max_per_transaction']}")
        print("\n🚀 Copy this Mandate ID to use in your Frontend Demo!")
    else:
        print("❌ Failed to create mandate:", data)

if __name__ == "__main__":
    seed_demo()
