import os
import json
from datetime import datetime
from google.cloud import firestore

db = firestore.Client()

def create_receipt(request):
    """
    HTTP Cloud Function
    - Expects JSON: { "order_id": 123, "email": "x@y.com", "total": 12.34 }
    - Writes a receipt document to Firestore
    - Returns: { "ok": true, "receipt_id": "...", "created_at": "..." }
    """
    try:
        data = request.get_json(silent=True) or {}
        order_id = data.get("order_id")
        email = data.get("email")
        total = data.get("total")

        if not order_id or not email or total is None:
            return ("Missing order_id/email/total", 400)

        created_at = datetime.utcnow().isoformat() + "Z"

        doc = {
            "order_id": order_id,
            "email": email,
            "total": total,
            "created_at": created_at,
            "source": "cloud_function"
        }

        ref = db.collection("receipts").add(doc)[1]

        return (json.dumps({
            "ok": True,
            "receipt_id": ref.id,
            "created_at": created_at
        }), 200, {"Content-Type": "application/json"})

    except Exception as e:
        return (f"Error: {str(e)}", 500)
