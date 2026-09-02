import razorpay
import os

# For hackathon speed, we use dummy keys if env vars aren't set. 
# You can replace these with your actual Razorpay Test Mode keys later.
KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_dummy_key_123")
KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "dummy_secret_456")

client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))

def create_order(amount_inr: float, receipt: str) -> dict:
    # Razorpay API expects amount in subunits (paise). 1 INR = 100 paise.
    data = {
        "amount": int(amount_inr * 100),
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1
    }
    try:
        return client.order.create(data=data)
    except Exception as e:
        return {"error": str(e)}


def verify_payment(order_id: str, payment_id: str, signature: str) -> bool:
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        return True
    except Exception:
        return False
