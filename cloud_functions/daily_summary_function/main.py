import json
from datetime import datetime
from google.cloud import firestore

db = firestore.Client()

def daily_sales_summary(request):
    """
    HTTP Cloud Function
    Saves a daily sales summary into Firestore.

    Expected JSON:
    {
        "date": "2026-02-02",
        "total_sales": 123.45,
        "order_count": 7
    }
    """

    try:
        data = request.get_json(silent=True) or {}

        date = data.get("date")
        total_sales = data.get("total_sales")
        order_count = data.get("order_count")

        if not date or total_sales is None or order_count is None:
            return ("Missing date / total_sales / order_count", 400)

        doc = {
            "date": date,
            "total_sales": float(total_sales),
            "order_count": int(order_count),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "source": "cloud_function_daily_summary"
        }

        db.collection("daily_summaries").document(date).set(doc)

        return (
            json.dumps({"ok": True, "date": date}),
            200,
            {"Content-Type": "application/json"}
        )

    except Exception as e:
        return (f"Error: {str(e)}", 500)
