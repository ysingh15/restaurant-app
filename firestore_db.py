import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from google.cloud import firestore
from google.api_core.exceptions import GoogleAPICallError, RetryError, ServiceUnavailable

# -----------------------
# SETTINGS
# -----------------------
COLLECTION_NAME = "order_events"
MAX_RETRIES = 3
RETRY_SLEEP_SECONDS = 1.0

# IMPORTANT:
# Use Firestore Native database id: "default"
# NOT "(default)" which is Datastore mode.
FIRESTORE_DB_ID = os.getenv("FIRESTORE_DB_ID", "default")

_client: Optional[firestore.Client] = None


def get_client() -> firestore.Client:
    """
    Creates and caches a Firestore client.
    Forces Firestore Native database by using database="default".
    """
    global _client
    if _client is not None:
        return _client

    # ✅ Force Firestore Native DB
    _client = firestore.Client(database=FIRESTORE_DB_ID)
    return _client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_order_event(
    order_id: Any,
    user_email: str,
    event: str,
    payload: Optional[Dict[str, Any]] = None
) -> str:
    """
    Writes an event document into Firestore Native. Returns the document id.

    - retries temporary errors
    - raises error if it still fails (so you KNOW it's broken)
    """
    db = get_client()

    doc = {
        "order_id": str(order_id),
        "user_email": user_email or "",
        "event": event,
        "payload": payload or {},
        "created_at": firestore.SERVER_TIMESTAMP,
        "created_at_iso": _now_iso(),
    }

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ref = db.collection(COLLECTION_NAME).document()
            ref.set(doc)
            return ref.id

        except (ServiceUnavailable, GoogleAPICallError, RetryError) as e:
            last_err = e
            print(f"[Firestore] write failed (attempt {attempt}/{MAX_RETRIES}): {e}")
            time.sleep(RETRY_SLEEP_SECONDS * attempt)

    raise RuntimeError(f"Firestore write failed after {MAX_RETRIES} attempts: {last_err}")
