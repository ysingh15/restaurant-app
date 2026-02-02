from flask import Blueprint, jsonify, request
from sql_db import SessionLocal
from models import MenuItem

api = Blueprint("api", __name__, url_prefix="/api")

@api.get("/menu")
def get_menu():
    with SessionLocal() as s:
        items = s.query(MenuItem).all()
    return jsonify([{
        "id": i.id, "name": i.name, "description": i.description,
        "category": i.category, "price": i.price
    } for i in items])

@api.post("/menu")
def create_menu():
    data = request.get_json(force=True)
    with SessionLocal() as s:
        item = MenuItem(
            name=data["name"],
            description=data.get("description", ""),
            category=data.get("category", "Main"),
            price=float(data["price"])
        )
        s.add(item)
        s.commit()
        s.refresh(item)
    return jsonify({"ok": True, "id": item.id}), 201
