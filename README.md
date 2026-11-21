# ADYPU Canteen — College Canteen Management System

A responsive Flask + SQLite web app with student ordering, admin operations, live status polling, loyalty points, QR menu access, sales analytics, recommendations and stock management.

## 1. Requirements
- Python 3.10+
- pip
- Internet connection for Bootstrap, Google Fonts, Chart.js and demo food photos (the core app runs locally).

## 2. Setup

```bash
# Open the ADYPU Canteen folder
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000
OPEN :- https://adypu-canteen.onrender.com

## 3. Demo administrator
 Email: `admin@adypucanteen.local`
- Password: `Admin@123`

Change this password and the Flask SECRET_KEY before any real deployment. Register a normal student account from the app.

## 4. Main workflows
1. Register or log in as a student.
2. Open Menu, add items and place an order.
3. Open My orders to see status; the page polls for status updates every 5 seconds.
4. Sign in as admin in another browser/session to update the order status.
5. Admin dashboard shows sales, student count, order count, popular items and low-stock count.
6. Admin → Inventory lets you add items, update stock and hide menu items.
7. `/qr` generates a QR image pointing to the public menu URL. For a deployed app, configure your production domain first.

## 5. Notes and next steps
- Payments are intentionally not processed; checkout is a demo order placement flow. Integrate a payment provider such as Razorpay only after configuring merchant credentials and webhook verification.
- QR currently opens the menu; add table/seat identifiers if you want table-specific ordering.
- Recommendations use transparent purchase-category affinity and popularity fallback. This is a lightweight local recommender, not a hosted generative AI service.
- For production: add CSRF protection, rate limiting, email verification, password reset, audit logs, database migrations, HTTPS, secure cookies, backups and a production WSGI server. Do not deploy Flask's debug server.
- The demo database is created automatically as `ADYPU Canteen.db`.
