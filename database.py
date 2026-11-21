import sqlite3
from flask import current_app, g
from werkzeug.security import generate_password_hash

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student',
        points INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        image TEXT,
        stock INTEGER NOT NULL DEFAULT 0,
        available INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Placed',
        points_earned INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        menu_item_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id),
        FOREIGN KEY(menu_item_id) REFERENCES menu_items(id)
    );
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        menu_item_id INTEGER NOT NULL,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(menu_item_id) REFERENCES menu_items(id)
    );
    """)
    
    admin_email = "admin@adypucanteen.local"
    admin = db.execute(
        "SELECT id FROM users WHERE email=?",
        (admin_email,)
    ).fetchone()

    if not admin:
        db.execute(
            "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
            (
                "ADYPU Canteen Admin",
                admin_email,
                generate_password_hash("Admin@123"),
                "admin"
            )
        )

    count = db.execute("SELECT COUNT(*) AS n FROM menu_items").fetchone()["n"]
    if count == 0:
        demo = [
            ("Classic Veg Burger","Crispy patty, lettuce and house sauce","Burgers",79,"https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=700",35),
            ("Paneer Tikka Wrap","Smoky paneer with mint chutney","Wraps",99,"https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=700",25),
            ("Margherita Pizza","Cheese, basil and tomato","Pizza",129,"https://images.unsplash.com/photo-1579751626657-72bc17010498?w=700",20),
            ("Masala Fries","Golden fries tossed in campus masala","Sides",59,"https://images.unsplash.com/photo-1573080496219-bb080dd4f877?w=700",40),
            ("Cold Coffee","Chilled coffee with creamy foam","Drinks",69,"https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=700",30),
            ("Veg Hakka Noodles","Wok-tossed noodles and vegetables","Meals",109,"https://images.unsplash.com/photo-1585032226651-759b368d7246?w=700",18),
        ]
        db.executemany("INSERT INTO menu_items(name,description,category,price,image,stock) VALUES(?,?,?,?,?,?)", demo)
    db.commit()
