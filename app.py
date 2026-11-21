import io, os, sqlite3, json
import urllib.request
import urllib.error
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
from config import Config
from database import get_db, close_db, init_db

app = Flask(__name__)
app.config.from_object(Config)
app.teardown_appcontext(close_db)

def send_notification_email(to_email, subject, message):
    api_key = os.environ.get("BREVO_API_KEY")

    if not api_key:
        print("BREVO_API_KEY is missing.")
        return

    payload = {
        "sender": {
            "name": "ADYPU Canteen",
            "email": "adypucanteen@gmail.com"
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": message
    }

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            print("Brevo email sent:", response.status)
    except Exception as e:
        print("Brevo email failed:", e)

with app.app_context():
    init_db()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_user():
    return {"current_user": get_db().execute("SELECT * FROM users WHERE id=?", (session.get("user_id"),)).fetchone() if session.get("user_id") else None}

@app.route("/")
def index():
    db = get_db()
    items = db.execute("SELECT * FROM menu_items WHERE available=1 AND stock>0 ORDER BY id DESC LIMIT 6").fetchall()
    return render_template("index.html", items=items)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name, email, password = request.form.get("name","").strip(), request.form.get("email","").strip().lower(), request.form.get("password","")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email and a password of at least 8 characters.", "danger")
        else:
            try:
                db=get_db()
                db.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)",(name,email,generate_password_hash(password)))
                db.commit()
                flash("Account created! Please sign in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.", "danger")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = get_db().execute(
            "SELECT * FROM users WHERE email=?",
            (request.form.get("email", "").strip().lower(),)
        ).fetchone()

        if user and check_password_hash(
            user["password_hash"], request.form.get("password", "")
        ):
            session.clear()
            session.update(
                user_id=user["id"],
                role=user["role"],
                name=user["name"]
            )

            if user["role"] == "student":
                try:
                    send_notification_email(
                        user["email"],
                        "Welcome to ADYPU Canteen!",
                        f"Hello {user['name']},\n\n"
                        "You have successfully logged in to ADYPU Canteen.\n"
                        "Enjoy ordering your favourite food!"
                    )
                except Exception as e:
                    print("Login email notification failed:", e)

            return redirect(
                url_for("admin_dashboard")
                if user["role"] == "admin"
                else url_for("menu")
            )

        flash("Incorrect email or password.", "danger")

    return render_template("auth.html", mode="login")

@app.route("/menu")
def menu():
    category=request.args.get("category","")
    q=request.args.get("q","").strip()
    sql="SELECT * FROM menu_items WHERE available=1 AND stock>0"
    params=[]
    if category: sql+=" AND category=?"; params.append(category)
    if q: sql+=" AND (name LIKE ? OR description LIKE ?)"; params += [f"%{q}%",f"%{q}%"]
    db=get_db()
    items=db.execute(sql+" ORDER BY category,name",params).fetchall()
    categories=[r["category"] for r in db.execute("SELECT DISTINCT category FROM menu_items ORDER BY category")]
    return render_template("menu.html",items=items,categories=categories,selected=category,q=q)

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    import json
    try: cart=json.loads(request.form.get("cart","{}"))
    except Exception: cart={}
    if not isinstance(cart,dict) or not cart:
        flash("Your cart is empty.", "warning"); return redirect(url_for("menu"))
    db=get_db(); lines=[]; total=0
    for key, qty in cart.items():
        try: item_id, qty=int(key), int(qty)
        except Exception: continue
        if qty<1 or qty>50: continue
        item=db.execute("SELECT * FROM menu_items WHERE id=? AND available=1",(item_id,)).fetchone()
        if not item or item["stock"]<qty:
            flash(f"Not enough stock for {item['name'] if item else 'an item'}. Please update your cart.", "danger")
            return redirect(url_for("menu"))
        lines.append((item,qty)); total += item["price"]*qty
    if not lines:
        flash("No valid items in your cart.", "warning"); return redirect(url_for("menu"))
    points=int(total//10)
    cur=db.execute("INSERT INTO orders(user_id,total,status,points_earned) VALUES(?,?,?,?)",(session["user_id"],total,"Placed",points))
    order_id=cur.lastrowid
    for item,qty in lines:
        db.execute("INSERT INTO order_items(order_id,menu_item_id,item_name,quantity,unit_price) VALUES(?,?,?,?,?)",(order_id,item["id"],item["name"],qty,item["price"]))
        db.execute("UPDATE menu_items SET stock=stock-? WHERE id=?",(qty,item["id"]))
    db.execute("UPDATE users SET points=points+? WHERE id=?",(points,session["user_id"]))
    db.commit()
    db.commit()

    user = db.execute(
         "SELECT name, email FROM users WHERE id=?",
         (session["user_id"],)
    ).fetchone()

    send_notification_email(
         user["email"],
         f"Order #{order_id} placed successfully!",
         f"Hello {user['name']},\n\n"
         f"Your order #{order_id} has been placed successfully.\n"
         f"Total amount: Rs. {total:.2f}\n"
         "Thank you for ordering from ADYPU Canteen!"
)

    return redirect(url_for("order_detail",order_id=order_id))
@app.route("/orders")
@login_required
def orders():
    rows=get_db().execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",(session["user_id"],)).fetchall()
    return render_template("orders.html",orders=rows)

@app.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    db=get_db()
    order=db.execute("SELECT o.*,u.name FROM orders o JOIN users u ON u.id=o.user_id WHERE o.id=?",(order_id,)).fetchone()
    if not order or (session["role"]!="admin" and order["user_id"]!=session["user_id"]): abort(404)
    lines=db.execute("SELECT * FROM order_items WHERE order_id=?",(order_id,)).fetchall()
    return render_template("order_detail.html",order=order,lines=lines)

@app.route("/api/orders/<int:order_id>")
@login_required
def order_status(order_id):
    order=get_db().execute("SELECT status FROM orders WHERE id=? AND user_id=?",(order_id,session["user_id"])).fetchone()
    if not order: abort(404)
    return jsonify(status=order["status"])

@app.route("/rewards")
@login_required
def rewards():
    user=get_db().execute("SELECT points FROM users WHERE id=?",(session["user_id"],)).fetchone()
    return render_template("rewards.html",points=user["points"])

@app.route("/recommendations")
@login_required
def recommendations():
    db=get_db()
    # Simple explainable recommender: category affinity from past purchases, then popularity.
    fav=db.execute("""SELECT m.category, COUNT(*) n FROM order_items oi
        JOIN orders o ON o.id=oi.order_id JOIN menu_items m ON m.id=oi.menu_item_id
        WHERE o.user_id=? GROUP BY m.category ORDER BY n DESC LIMIT 1""",(session["user_id"],)).fetchone()
    if fav:
        items=db.execute("SELECT * FROM menu_items WHERE available=1 AND stock>0 AND category=? ORDER BY price LIMIT 6",(fav["category"],)).fetchall()
        reason=f"Because you have ordered {fav['category']} before"
    else:
        items=db.execute("""SELECT m.*, COALESCE(SUM(oi.quantity),0) popularity FROM menu_items m
            LEFT JOIN order_items oi ON oi.menu_item_id=m.id
            WHERE m.available=1 AND m.stock>0 GROUP BY m.id ORDER BY popularity DESC LIMIT 6""").fetchall()
        reason="Popular picks around campus"
    return render_template("recommendations.html",items=items,reason=reason)

@app.route("/qr")
def qr_code():
    target=url_for("menu",_external=True)
    img=qrcode.make(target); buf=io.BytesIO(); img.save(buf,format="PNG"); buf.seek(0)
    return send_file(buf,mimetype="image/png",download_name="ADYPU Canteen-menu-qr.png")

@app.route("/admin")
@admin_required
def admin_dashboard():
    db=get_db()
    stats={
        "revenue":db.execute("SELECT COALESCE(SUM(total),0) v FROM orders WHERE status!='Cancelled'").fetchone()["v"],
        "orders":db.execute("SELECT COUNT(*) v FROM orders").fetchone()["v"],
        "students":db.execute("SELECT COUNT(*) v FROM users WHERE role='student'").fetchone()["v"],
        "low":db.execute("SELECT COUNT(*) v FROM menu_items WHERE stock<=5").fetchone()["v"],
    }
    recent=db.execute("SELECT o.*,u.name FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.id DESC LIMIT 8").fetchall()
    daily=db.execute("SELECT date(created_at) day, SUM(total) revenue FROM orders WHERE status!='Cancelled' GROUP BY date(created_at) ORDER BY day DESC LIMIT 7").fetchall()
    popular=db.execute("SELECT item_name,SUM(quantity) qty FROM order_items GROUP BY item_name ORDER BY qty DESC LIMIT 5").fetchall()
    return render_template("admin.html",stats=stats,recent=recent,daily=list(reversed(daily)),popular=popular)

@app.route("/admin/items",methods=["GET","POST"])
@admin_required
def admin_items():
    db=get_db()
    if request.method=="POST":
        name=request.form.get("name","").strip(); desc=request.form.get("description","").strip()
        category=request.form.get("category","").strip(); image=request.form.get("image","").strip()
        try: price=float(request.form.get("price",0)); stock=int(request.form.get("stock",0))
        except ValueError: price=-1; stock=-1
        if not name or not category or price<=0 or stock<0:
            flash("Please enter valid item details.", "danger")
        else:
            db.execute("INSERT INTO menu_items(name,description,category,price,image,stock) VALUES(?,?,?,?,?,?)",(name,desc,category,price,image,stock)); db.commit()
            flash("Menu item added.", "success")
        return redirect(url_for("admin_items"))
    items=db.execute("SELECT * FROM menu_items ORDER BY category,name").fetchall()
    return render_template("admin_items.html",items=items)

@app.route("/admin/items/<int:item_id>/stock",methods=["POST"])
@admin_required
def update_stock(item_id):
    try: stock=max(0,int(request.form.get("stock",0)))
    except ValueError: stock=0
    db=get_db(); db.execute("UPDATE menu_items SET stock=? WHERE id=?",(stock,item_id)); db.commit()
    flash("Inventory updated.", "success")
    return redirect(url_for("admin_items"))

@app.route("/admin/items/<int:item_id>/delete",methods=["POST"])
@admin_required
def delete_item(item_id):
    db=get_db(); db.execute("UPDATE menu_items SET available=0 WHERE id=?",(item_id,)); db.commit()
    flash("Item hidden from the menu.", "info")
    return redirect(url_for("admin_items"))

@app.route("/admin/orders")
@admin_required
def admin_orders():
    rows=get_db().execute("SELECT o.*,u.name FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.id DESC").fetchall()
    return render_template("admin_orders.html",orders=rows)

@app.route("/admin/orders/<int:order_id>/status",methods=["POST"])
@admin_required
def update_order(order_id):
    status=request.form.get("status")
    if status not in ["Placed","Preparing","Ready","Completed","Cancelled"]: abort(400)
    db=get_db(); db.execute("UPDATE orders SET status=? WHERE id=?",(status,order_id)); db.commit()
    flash("Order status updated.", "success")
    return redirect(url_for("admin_orders"))

if __name__=="__main__":
    app.run(debug=True)
