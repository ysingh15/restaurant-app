import os
import re
import requests
from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, current_app
)
from werkzeug.utils import secure_filename
from sqlalchemy import func

from sql_db import SessionLocal
from models import User, MenuItem, Order, OrderItem
from auth import hash_password, verify_password, login_required, admin_required
from firestore_db import log_order_event
from google.cloud import secretmanager


web = Blueprint("web", __name__)

import google.auth
from google.cloud import secretmanager

def get_secret(name: str) -> str | None:
    """
    Read a secret from Google Secret Manager.
    Falls back to environment variable for local development.
    """
    # Local dev fallback
    env_val = os.environ.get(name)
    if env_val:
        return env_val

    try:
        creds, project_id = google.auth.default()
        if not project_id:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

        if not project_id:
            return None

        client = secretmanager.SecretManagerServiceClient(credentials=creds)
        secret_path = f"projects/{project_id}/secrets/{name}/versions/latest"
        resp = client.access_secret_version(request={"name": secret_path})
        return resp.payload.data.decode("utf-8").strip()

    except Exception as e:
        print(f"Secret Manager read failed for {name}: {e}")
        return None

# -----------------------
# Cloud Function helper (Daily Summary)
# -----------------------
def send_daily_summary(date_str, total_sales, order_count):
    url = get_secret("DAILY_SUMMARY_FUNCTION_URL")
    print("DAILY_SUMMARY_FUNCTION_URL =", url)

    if not url:
        print("DAILY_SUMMARY_FUNCTION_URL not set; skipping.")
        return

    try:
        requests.post(
            url,
            json={
                "date": date_str,
                "total_sales": float(total_sales),
                "order_count": int(order_count),
            },
            timeout=10,
        )
    except Exception as e:
        print("Daily summary function failed:", e)


# -----------------------
# Cloud Function helper (Receipt)
# -----------------------
def tell_robot(order_id, email, total):
    """
    Calls receipt Cloud Function after payment
    """
    robot_house = get_secret("RECEIPT_FUNCTION_URL")

    if not robot_house:
        print("RECEIPT_FUNCTION_URL not set; skipping receipt.")
        return

    try:
        resp = requests.post(
            robot_house,
            json={
                "order_id": int(order_id),
                "email": str(email or ""),
                "total": float(total),
            },
            timeout=10,
        )
        print("Receipt:", resp.status_code, resp.text)
    except Exception as e:
        print("Receipt function failed:", e)


# -----------------------
# Admin: Run Daily Summary (calls Cloud Function #2)
# -----------------------
@web.get("/admin/summary/run")
@login_required
@admin_required
def admin_run_daily_summary():
    today = datetime.now(timezone.utc).date().isoformat()

    with SessionLocal() as s:
        order_count = s.query(func.count(Order.id)).scalar() or 0

        total_sales = (
            s.query(func.sum(OrderItem.qty * OrderItem.unit_price))
            .join(Order, Order.id == OrderItem.order_id)
            .scalar()
        ) or 0.0

    send_daily_summary(today, total_sales, order_count)

    flash(
        f"Daily summary sent for {today} "
        f"(orders: {order_count}, sales: £{float(total_sales):.2f})"
    )

    return redirect(url_for("web.admin_menu"))


# -----------------------
# Home
# -----------------------
@web.get("/")
def index():
    return render_template("index.html")


# -----------------------
# Auth
# -----------------------
@web.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]
        role = request.form.get("role", "customer")

        with SessionLocal() as s:
            if s.query(User).filter_by(email=email).first():
                flash("Email already exists.")
                return redirect(url_for("web.register"))

            u = User(email=email, password_hash=hash_password(pw), role=role)
            s.add(u)
            s.commit()

        flash("Account created. Please login.")
        return redirect(url_for("web.login"))

    return render_template("register.html")


@web.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pw = request.form["password"]

        with SessionLocal() as s:
            u = s.query(User).filter_by(email=email).first()
            if not u or not verify_password(pw, u.password_hash):
                flash("Invalid login.")
                return redirect(url_for("web.login"))

            session["user_id"] = u.id
            session["email"] = u.email
            session["role"] = u.role

        flash("Logged in.")
        return redirect(url_for("web.menu"))

    return render_template("login.html")


@web.get("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("web.index"))
# -----------------------
# Menu (with category filter)
# -----------------------
@web.get("/menu")
def menu():
    selected = request.args.get("category", "").strip()

    with SessionLocal() as s:
        categories = [
            c[0]
            for c in s.query(MenuItem.category).distinct().order_by(MenuItem.category).all()
            if c[0]
        ]

        q = s.query(MenuItem)
        if selected:
            q = q.filter(MenuItem.category == selected)

        items = q.order_by(MenuItem.category, MenuItem.name).all()

    return render_template("menu.html", items=items, categories=categories, selected=selected)


# -----------------------
# Cart
# -----------------------
@web.post("/cart/add/<int:item_id>")
@login_required
def cart_add(item_id: int):
    cart = session.get("cart", {})
    cart[str(item_id)] = int(cart.get(str(item_id), 0)) + 1
    session["cart"] = cart
    flash("Added to cart.")
    return redirect(url_for("web.menu"))


@web.get("/cart")
@login_required
def cart_view():
    cart = session.get("cart", {})
    item_ids = [int(k) for k in cart.keys()] if cart else []

    with SessionLocal() as s:
        items = s.query(MenuItem).filter(MenuItem.id.in_(item_ids)).all() if item_ids else []
        items_map = {i.id: i for i in items}

    lines = []
    total = 0.0
    for k, qty in cart.items():
        mi = items_map.get(int(k))
        if mi:
            qty = int(qty)
            line_total = float(mi.price) * qty
            total += line_total
            lines.append({"item": mi, "qty": qty, "line_total": line_total})

    return render_template("cart.html", lines=lines, total=total)


@web.post("/cart/update/<int:item_id>")
@login_required
def cart_update(item_id: int):
    action = request.form.get("action", "")
    cart = session.get("cart", {})

    key = str(item_id)
    qty = int(cart.get(key, 0))

    if action == "inc":
        qty += 1
    elif action == "dec":
        qty -= 1

    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = qty

    session["cart"] = cart
    return redirect(url_for("web.cart_view"))


@web.post("/cart/remove/<int:item_id>")
@login_required
def cart_remove(item_id: int):
    cart = session.get("cart", {})
    cart.pop(str(item_id), None)
    session["cart"] = cart
    return redirect(url_for("web.cart_view"))


# -----------------------
# UK postcode validation
# -----------------------
UK_POSTCODE_RE = re.compile(
    r"^(GIR 0AA|(?:[A-Z]{1,2}\d{1,2}[A-Z]?)\s?\d[A-Z]{2})$",
    re.IGNORECASE,
)


def _is_valid_postcode(pc: str) -> bool:
    pc = (pc or "").strip().upper()
    return bool(UK_POSTCODE_RE.match(pc))


# -----------------------
# Checkout + Payment
# -----------------------
@web.get("/checkout")
@login_required
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.")
        return redirect(url_for("web.cart_view"))

    checkout_data = session.get("checkout", {})
    return render_template("checkout.html", data=checkout_data)


@web.post("/checkout")
@login_required
def checkout_post():
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()
    address1 = request.form.get("address1", "").strip()
    address2 = request.form.get("address2", "").strip()
    city = request.form.get("city", "").strip()
    postcode = request.form.get("postcode", "").strip().upper()

    errors = []
    if not full_name:
        errors.append("Full name is required.")
    if not phone:
        errors.append("Phone number is required.")
    if not address1:
        errors.append("Address line 1 is required.")
    if not city:
        errors.append("Town/City is required.")
    if not _is_valid_postcode(postcode):
        errors.append("Please enter a valid UK postcode.")

    if errors:
        for e in errors:
            flash(e)
        session["checkout"] = {
            "full_name": full_name,
            "phone": phone,
            "address1": address1,
            "address2": address2,
            "city": city,
            "postcode": postcode,
        }
        return redirect(url_for("web.checkout"))

    session["checkout"] = {
        "full_name": full_name,
        "phone": phone,
        "address1": address1,
        "address2": address2,
        "city": city,
        "postcode": postcode,
    }
    return redirect(url_for("web.payment"))


@web.get("/payment")
@login_required
def payment():
    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.")
        return redirect(url_for("web.cart_view"))

    if not session.get("checkout"):
        flash("Please enter delivery details first.")
        return redirect(url_for("web.checkout"))

    return render_template("payment.html")


@web.post("/payment")
@login_required
def payment_post():
    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty.")
        return redirect(url_for("web.cart_view"))

    checkout_data = session.get("checkout")
    if not checkout_data:
        flash("Please enter delivery details first.")
        return redirect(url_for("web.checkout"))

    # server-side validation
    card_name = request.form.get("card_name", "").strip()
    card_number = request.form.get("card_number", "").replace(" ", "").strip()
    exp = request.form.get("exp", "").strip()
    cvc = request.form.get("cvc", "").strip()
    billing_postcode = request.form.get("billing_postcode", "").strip().upper()
    agree = request.form.get("agree")

    errors = []
    if not card_name:
        errors.append("Name on card is required.")
    if not (card_number.isdigit() and 12 <= len(card_number) <= 19):
        errors.append("Card number looks invalid (digits only).")
    if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", exp):
        errors.append("Expiry must be in MM/YY format.")
    if not (cvc.isdigit() and len(cvc) in (3, 4)):
        errors.append("CVC looks invalid (3 or 4 digits).")
    if not _is_valid_postcode(billing_postcode):
        errors.append("Billing postcode must be a valid UK postcode.")
    if not agree:
        errors.append("You must confirm you are authorised to use this payment method.")

    if errors:
        for e in errors:
            flash(e)
        return redirect(url_for("web.payment"))

    # ✅ Create order AFTER payment
    item_ids = [int(k) for k in cart.keys()]

    with SessionLocal() as s:
        items = s.query(MenuItem).filter(MenuItem.id.in_(item_ids)).all()
        items_map = {i.id: i for i in items}

        # compute total for receipt
        total = 0.0
        for k, qty in cart.items():
            mi = items_map.get(int(k))
            if mi:
                total += float(mi.price) * int(qty)

        order = Order(user_id=session["user_id"])
        s.add(order)
        s.flush()

        for k, qty in cart.items():
            mi = items_map.get(int(k))
            if mi:
                s.add(
                    OrderItem(
                        order_id=order.id,
                        menu_item_id=mi.id,
                        qty=int(qty),
                        unit_price=float(mi.price),
                    )
                )

        s.commit()
        order_id = order.id

    # Firestore log (your existing logging project)
    try:
        doc_id = log_order_event(
            order_id=order_id,
            user_email=session.get("email", ""),
            event="PAYMENT_AUTHORISED",
            payload={"delivery": checkout_data},
        )
        print("✅ Firestore wrote document:", doc_id)
    except Exception as e:
        print("Firestore log failed:", e)

    # ✅ Call Cloud Function (receipt)
    tell_robot(order_id, session.get("email", ""), total)

    # Clear cart + finish
    session["cart"] = {}
    flash(f"Payment successful. Order #{order_id} placed!")
    return redirect(url_for("web.orders"))


# -----------------------
# Orders
# -----------------------
@web.post("/order/place")
@login_required
def place_order():
    flash("Please go to checkout and complete payment before placing an order.")
    return redirect(url_for("web.checkout"))


@web.get("/orders")
@login_required
def orders():
    with SessionLocal() as s:
        orders_list = (
            s.query(Order)
            .filter_by(user_id=session["user_id"])
            .order_by(Order.created_at.desc())
            .all()
        )
    return render_template("orders.html", orders=orders_list)


# -----------------------
# Image uploads (Admin)
# -----------------------
ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "webp"}


def save_image_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXTS:
        raise ValueError("Invalid file type. Use png, jpg, jpeg, webp.")

    images_dir = os.path.join(current_app.root_path, "static", "images")
    os.makedirs(images_dir, exist_ok=True)

    base, dot, ext2 = filename.rpartition(".")
    if not base:
        base = "image"
        ext2 = ext

    candidate = filename
    n = 1
    while os.path.exists(os.path.join(images_dir, candidate)):
        candidate = f"{base}_{n}.{ext2}"
        n += 1

    file_storage.save(os.path.join(images_dir, candidate))
    return candidate


# -----------------------
# Admin: CRUD Menu
# -----------------------
@web.get("/admin/menu")
@login_required
@admin_required
def admin_menu():
    with SessionLocal() as s:
        items = s.query(MenuItem).order_by(MenuItem.id.desc()).all()
    return render_template("admin_menu.html", items=items)


def _parse_price(value: str) -> float:
    v = (value or "").strip().replace("£", "").replace(",", ".")
    return float(v)


@web.post("/admin/menu/create")
@login_required
@admin_required
def admin_menu_create():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "Main").strip()
    description = request.form.get("description", "").strip()

    try:
        price = _parse_price(request.form.get("price", ""))
    except Exception:
        flash("Price must be a number like 9.99 (don’t include £).")
        return redirect(url_for("web.admin_menu"))

    if not name:
        flash("Name is required.")
        return redirect(url_for("web.admin_menu"))

    image_file = request.files.get("image")
    try:
        image_name = save_image_upload(image_file)
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("web.admin_menu"))

    with SessionLocal() as s:
        s.add(
            MenuItem(
                name=name,
                category=category,
                description=description,
                price=price,
                image=image_name,
            )
        )
        s.commit()

    flash("Menu item created.")
    return redirect(url_for("web.admin_menu"))


@web.post("/admin/menu/update/<int:item_id>")
@login_required
@admin_required
def admin_menu_update(item_id: int):
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "Main").strip()
    description = request.form.get("description", "").strip()

    try:
        price = _parse_price(request.form.get("price", ""))
    except Exception:
        flash("Price must be a number like 9.99 (don’t include £).")
        return redirect(url_for("web.admin_menu"))

    image_file = request.files.get("image")
    try:
        new_image_name = save_image_upload(image_file)
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("web.admin_menu"))

    with SessionLocal() as s:
        item = s.get(MenuItem, item_id)
        if not item:
            flash("Item not found.")
            return redirect(url_for("web.admin_menu"))

        item.name = name
        item.category = category
        item.description = description
        item.price = price

        if new_image_name:
            item.image = new_image_name

        s.commit()

    flash("Menu item updated.")
    return redirect(url_for("web.admin_menu"))


@web.post("/admin/menu/delete/<int:item_id>")
@login_required
@admin_required
def admin_menu_delete(item_id: int):
    with SessionLocal() as s:
        item = s.get(MenuItem, item_id)
        if item:
            s.delete(item)
            s.commit()

    flash("Menu item deleted.")
    return redirect(url_for("web.admin_menu"))
