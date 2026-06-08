"""
Beacon Digital Solutions - Backend (Flask + SQLite)

PRIMARY CURRENT USE (as of pause on payments work):
- Own and maintain community email list from all "Join the Community" buttons on the site.
- Collect structured feedback (bugs, features, general) from users via the public form on /support.
- Admin UI at /admin/contacts (with CSV export) and /admin/feedback (triage + backlog management).

The Stripe + automatic license key issuance code is still present but the direct web subscription flow is PAUSED.

To use community + feedback locally:
  export ADMIN_PASSWORD=your-strong-password
  PORT=5001 python3 app.py
Then visit:
  http://localhost:5001/admin/contacts
  http://localhost:5001/admin/feedback   (login with admin / your ADMIN_PASSWORD)

Website forms now POST here instead of Formspree so you own every record.

See README.md for full local testing steps + how to update the endpoint URLs when you deploy this backend.

---

Payments / licensing quick notes (paused):
- The code supports Stripe Checkout + automatic BB-XXXX license generation on checkout.session.completed.
- Webhook was the last missing piece in local test (export STRIPE_WEBHOOK_SECRET=whsec_... from stripe listen).
- Mac app side (AppConstants + LicenseManager + SettingsView) still needs the activation UI wired if you resume later.
"""

from flask import Flask, request, jsonify
import os
import sqlite3
import uuid
import hmac
import hashlib
import time
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# Allow CORS for local testing (remove in production)
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

from functools import wraps

def check_auth(username, password):
    """Check if username/password combination is valid."""
    return username == 'admin' and password == os.environ.get('ADMIN_PASSWORD', 'change-this-password-now')

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return 'Unauthorized. Use admin / your ADMIN_PASSWORD', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}
        return f(*args, **kwargs)
    return decorated

# ==================== CONFIG ====================
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:5000")

# For emails (get free key at resend.com)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

# Premium price ID from Stripe (create a $8/mo recurring product in Stripe Dashboard)
PREMIUM_PRICE_ID = os.environ.get("PREMIUM_PRICE_ID", "price_1Tg54DLG5yvcqnWHjA9K29XZ")

# How many devices a single license can be activated on
# How long before the app should re-validate with the server (in days)
VALIDATION_INTERVAL_DAYS = 30

# Simple local SQLite DB (use Postgres in production)
DB_PATH = "licenses.db"

# Secret for signing licenses (generate a long random string and keep it secret)
# For quick local test you can use this one (change for production):
LICENSE_SIGNING_SECRET = os.environ.get("LICENSE_SIGNING_SECRET", "test-secret-please-change-this-to-a-long-random-string-for-prod-1234567890abcdef")

# ==================== DATABASE ====================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            stripe_subscription_id TEXT,
            stripe_customer_id TEXT,
            status TEXT DEFAULT 'active',  -- active, canceled, expired
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            devices TEXT DEFAULT '[]'     -- JSON array of device fingerprints
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            signup_date TEXT,
            source TEXT DEFAULT 'website',
            tags TEXT,  -- comma-separated or JSON
            notes TEXT,
            subscribed INTEGER DEFAULT 1
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            tool TEXT DEFAULT 'beacon_budget',
            type TEXT,  -- bug, feature, general, praise, other
            title TEXT,
            description TEXT,
            status TEXT DEFAULT 'new',  -- new, triaged, in_progress, done, wontfix
            priority TEXT DEFAULT 'medium',  -- low, medium, high, critical
            created_at TEXT,
            updated_at TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==================== HELPERS ====================
def generate_license_key():
    """Generate a human-friendly unique serial number."""
    raw = str(uuid.uuid4()).replace('-', '')[:16].upper()
    # Add a check digit / prefix for professionalism
    key = f"BB-{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}"
    return key

def sign_license(license_key: str, email: str) -> str:
    """Create a signature so the app can do basic offline verification."""
    message = f"{license_key}:{email}".encode()
    signature = hmac.new(LICENSE_SIGNING_SECRET.encode(), message, hashlib.sha256).hexdigest()[:16]
    return signature

# Device fingerprinting has been removed per your request.
# Licensing is now based purely on (email + license_key) + Stripe subscription status.

def is_subscription_active(license_row):
    """In production you should also call Stripe API to double-check."""
    return license_row["status"] == "active"

# ==================== STRIPE CHECKOUT ====================
@app.route('/create-checkout', methods=['POST'])
def create_checkout():
    """Called by the website when user clicks Subscribe."""
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    data = request.get_json() or {}
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=email,
            line_items=[{
                "price": PREMIUM_PRICE_ID,
                "quantity": 1,
            }],
            success_url=f"{BACKEND_BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BACKEND_BASE_URL}/cancel",
            metadata={"product": "beacon_budget_premium"}
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/success')
def success():
    """Simple success page after Stripe Checkout."""
    session_id = request.args.get("session_id")
    return f"""
    <html><body style="font-family: system-ui; padding: 40px; max-width: 600px; margin: auto;">
        <h1>Thank you!</h1>
        <p>Your payment was successful.</p>
        <p><strong>For this local test:</strong> Look in the Flask terminal (the one running the backend) for the line with "License = BB-XXXX-XXXX-XXXX-XXXX". Copy that key (the BB- part).</p>
        <p>In your Mac app (Beacon Budget), go to Settings → Premium and use the "Activate with License Key" UI (you'll add it) to enter the email and key. It will call the local backend to activate.</p>
        <p><a href="https://beacondigitalsolutionsllc.com/beaconbudget">Back to Beacon Budget page</a></p>
    </body></html>
    """

@app.route('/cancel')
def cancel():
    return "Checkout canceled. <a href='https://beacondigitalsolutionsllc.com/beaconbudget'>Return to site</a>"

# ==================== COMMUNITY & FEEDBACK (for maintaining records and backlog) ====================

@app.route('/community/signup', methods=['POST'])
def community_signup():
    """Accept signups from website forms (or in-app later). Stores in DB for your records.
    You can later export CSV or sync to Buttondown/Resend for actual mailing.
    """
    email = request.form.get('email') or (request.json or {}).get('email')
    name = request.form.get('name') or (request.json or {}).get('name', '')
    source = request.form.get('source') or (request.json or {}).get('source', 'website_community')

    if not email or '@' not in email:
        return "Valid email required", 400

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO contacts (email, name, signup_date, source, subscribed)
            VALUES (?, ?, ?, ?, 1)
        ''', (email.lower().strip(), name.strip(), datetime.utcnow().isoformat(), source))
        conn.commit()
        print(f"New community signup: {email}")
    except sqlite3.IntegrityError:
        # Already exists, update source or just note
        c.execute('UPDATE contacts SET source = ? WHERE email = ?', (source, email.lower().strip()))
        conn.commit()
        print(f"Community signup duplicate (updated source): {email}")
    conn.close()

    # TODO: If you want, forward to Buttondown here using their API if you have a key.
    # For now, just stored centrally so you can export/manage.

    return "Thanks for joining the community! We'll be in touch.", 200

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    """Collect feedback/bugs from website or Mac app.
    Stores centrally so you can triage and build your backlog.
    """
    data = request.form or request.json or {}
    email = data.get('email', '').strip().lower()
    tool = data.get('tool', 'beacon_budget')
    type_ = data.get('type', 'general')  # bug, feature, praise, other
    title = data.get('title', 'No title').strip()
    description = data.get('description', '').strip()

    if not description:
        return "Description is required", 400

    conn = get_db()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute('''
        INSERT INTO feedback (email, tool, type, title, description, status, priority, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'new', 'medium', ?, ?)
    ''', (email or None, tool, type_, title, description, now, now))
    conn.commit()
    feedback_id = c.lastrowid
    conn.close()

    print(f"New feedback #{feedback_id} from {email or 'anonymous'}: {title} ({type_})")

    return f"Thank you! Feedback #{feedback_id} received. We'll review it soon.", 200

# Simple admin pages (protected with basic auth - set ADMIN_PASSWORD env var)
@app.route('/admin/contacts')
@requires_auth
def admin_contacts():
    conn = get_db()
    search = request.args.get('q', '').lower()
    if search:
        contacts = conn.execute(
            "SELECT * FROM contacts WHERE email LIKE ? OR name LIKE ? ORDER BY signup_date DESC",
            (f'%{search}%', f'%{search}%')
        ).fetchall()
    else:
        contacts = conn.execute("SELECT * FROM contacts ORDER BY signup_date DESC").fetchall()
    conn.close()

    html = f'''<html><head><title>Community Contacts</title>
    <style>body {{font-family: system-ui; margin: 20px;}} table {{border-collapse: collapse; width: 100%;}} th,td {{border:1px solid #ccc; padding:8px; text-align:left;}} th {{background:#f0f0f0;}}</style>
    </head><body>
    <h1>Community Members ({len(contacts)})</h1>
    <form method="get"><input name="q" placeholder="Search email or name" value="{search}"> <button>Search</button></form>
    <p><a href="/admin/feedback">View Feedback / Backlog</a> | <a href="/admin/contacts?export=1">Export CSV</a></p>
    <table><tr><th>Email</th><th>Name</th><th>Signed up</th><th>Source</th><th>Subscribed</th><th>Notes</th></tr>'''
    for c in contacts:
        sub = 'Yes' if c['subscribed'] else 'No'
        html += f"<tr><td>{c['email']}</td><td>{c['name'] or ''}</td><td>{c['signup_date'][:10]}</td><td>{c['source']}</td><td>{sub}</td><td>{c['notes'] or ''}</td></tr>"
    html += '</table></body></html>'

    if request.args.get('export'):
        # Simple CSV export
        import csv
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['email', 'name', 'signup_date', 'source', 'subscribed', 'notes'])
        for c in contacts:
            writer.writerow([c['email'], c['name'] or '', c['signup_date'], c['source'], c['subscribed'], c['notes'] or ''])
        return output.getvalue(), 200, {'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=contacts.csv'}

    return html

@app.route('/admin/feedback', methods=['GET', 'POST'])
@requires_auth
def admin_feedback():
    conn = get_db()
    if request.method == 'POST':
        fid = request.form.get('id')
        new_status = request.form.get('status')
        new_priority = request.form.get('priority')
        new_notes = request.form.get('notes', '')
        if fid and new_status:
            conn.execute('UPDATE feedback SET status=?, priority=?, notes=?, updated_at=? WHERE id=?',
                         (new_status, new_priority or 'medium', new_notes, datetime.utcnow().isoformat(), fid))
            conn.commit()
    search = request.args.get('q', '').lower()
    status_filter = request.args.get('status', '')
    query = "SELECT * FROM feedback"
    params = []
    where = []
    if search:
        where.append("(email LIKE ? OR title LIKE ? OR description LIKE ?)")
        params.extend([f'%{search}%']*3)
    if status_filter:
        where.append("status = ?")
        params.append(status_filter)
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY created_at DESC"
    feedback = conn.execute(query, params).fetchall()
    conn.close()

    html = f'''<html><head><title>Feedback & Backlog</title>
    <style>body {{font-family: system-ui; margin: 20px;}} table {{border-collapse: collapse; width: 100%;}} th,td {{border:1px solid #ccc; padding:6px; text-align:left; vertical-align:top;}} th {{background:#f0f0f0;}} .bug{{background:#ffeeee}} .feature{{background:#eeffee}}</style>
    </head><body>
    <h1>Feedback & Backlog ({len(feedback)})</h1>
    <p><a href="/admin/contacts">View Contacts</a></p>
    <form method="get">Search: <input name="q" value="{search}"> Status: <select name="status"><option value="">All</option><option value="new">New</option><option value="triaged">Triaged</option><option value="in_progress">In Progress</option><option value="done">Done</option><option value="wontfix">Won't Fix</option></select> <button>Filter</button></form>
    <table><tr><th>ID</th><th>Email</th><th>Tool / Type</th><th>Title / Desc</th><th>Status</th><th>Priority</th><th>Created</th><th>Notes / Update</th></tr>'''
    for f in feedback:
        cls = 'bug' if f['type']=='bug' else ('feature' if f['type']=='feature' else '')
        html += f'''<tr class="{cls}"><td>{f['id']}</td><td>{f['email'] or ''}</td><td>{f['tool']}<br><small>{f['type']}</small></td>
        <td><b>{f['title']}</b><br>{f['description'][:200]}{'...' if len(f['description'])>200 else ''}</td>
        <td>{f['status']}</td><td>{f['priority']}</td><td>{f['created_at'][:16]}</td>
        <td>
        <form method="post" style="margin:0">
            <input type="hidden" name="id" value="{f['id']}">
            <select name="status"><option value="new" {'selected' if f['status']=='new' else ''}>New</option><option value="triaged" {'selected' if f['status']=='triaged' else ''}>Triaged</option><option value="in_progress" {'selected' if f['status']=='in_progress' else ''}>In Progress</option><option value="done" {'selected' if f['status']=='done' else ''}>Done</option><option value="wontfix" {'selected' if f['status']=='wontfix' else ''}>Won't Fix</option></select>
            <select name="priority"><option value="low" {'selected' if f['priority']=='low' else ''}>Low</option><option value="medium" {'selected' if f['priority']=='medium' else ''}>Medium</option><option value="high" {'selected' if f['priority']=='high' else ''}>High</option><option value="critical" {'selected' if f['priority']=='critical' else ''}>Critical</option></select>
            <input name="notes" value="{f['notes'] or ''}" placeholder="Notes">
            <button type="submit">Update</button>
        </form>
        </td></tr>'''
    html += '</table><p>Statuses feed your backlog. Use this to prioritize and track fixes/features.</p></body></html>'
    return html

# ==================== STRIPE WEBHOOK (THE MAGIC) ====================
@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    payload = request.data
    sig_header = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError:
        return "Invalid signature", 400

    # Handle the events we care about
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_successful_payment(session)

    elif event['type'] == 'invoice.payment_succeeded':
        # Recurring payments
        invoice = event['data']['object']
        if invoice.get('subscription'):
            # You can update status here if needed
            pass

    elif event['type'] == 'customer.subscription.deleted':
        # User canceled
        subscription = event['data']['object']
        deactivate_license_by_subscription(subscription['id'])

    return jsonify({'status': 'success'}), 200

def handle_successful_payment(session):
    """Generate license + email it automatically."""
    email = session.get('customer_email') or session.get('customer_details', {}).get('email')
    subscription_id = session.get('subscription')
    customer_id = session.get('customer')

    if not email:
        print("No email on session – cannot fulfill")
        return

    conn = get_db()
    c = conn.cursor()

    # Check if they already have an active license for this subscription
    c.execute("SELECT * FROM licenses WHERE stripe_subscription_id = ?", (subscription_id,))
    existing = c.fetchone()
    if existing:
        conn.close()
        return

    license_key = generate_license_key()
    signature = sign_license(license_key, email)

    c.execute('''
        INSERT INTO licenses (license_key, email, stripe_subscription_id, stripe_customer_id, status)
        VALUES (?, ?, ?, ?, 'active')
    ''', (license_key, email, subscription_id, customer_id))
    conn.commit()
    conn.close()

    # Send email with the license
    send_license_email(email, license_key, signature)

    print(f"✅ License {license_key} created and emailed to {email}")

def deactivate_license_by_subscription(subscription_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE licenses SET status = 'canceled' WHERE stripe_subscription_id = ?", (subscription_id,))
    conn.commit()
    conn.close()
    print(f"License for subscription {subscription_id} marked as canceled")

# ==================== EMAIL (using Resend - very easy) ====================
def send_license_email(to_email: str, license_key: str, signature: str):
    if not RESEND_API_KEY:
        print(f"[DEV] Would email {to_email}: License = {license_key}")
        print(f"        Activation signature (for app): {signature}")
        return

    import requests
    try:
        requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": "Beacon Budget <licenses@beacondigitalsolutionsllc.com>",
                "to": to_email,
                "subject": "Your Beacon Budget Premium License Key",
                "html": f"""
                <p>Thank you for supporting Beacon Budget!</p>
                <p>Your unique license key is:</p>
                <h2 style="font-family: monospace; background:#f4f4f4; padding:12px; border-radius:6px;">{license_key}</h2>
                <p><strong>Important:</strong> This key is tied to your email. To activate:</p>
                <ol>
                    <li>Open Beacon Budget</li>
                    <li>Go to Settings → Premium</li>
                    <li>Enter your email and the license key above</li>
                </ol>
                <p>You can activate on multiple devices using the same email + key.</p>
                <p>If you ever need to cancel, use the link in your Stripe receipt or email us.</p>
                <p>— The Beacon Digital Solutions team</p>
                """
            }
        )
    except Exception as e:
        print("Email send failed:", e)

# ==================== APP ACTIVATION & VALIDATION API ====================
# Simple email + license key model. No device fingerprinting.
# The main protections are:
# - License is tied to the email used at purchase
# - Backend checks that the Stripe subscription is still active
# - App should re-validate periodically (recommended: on every launch or every few days)

@app.route('/activate', methods=['POST'])
def activate_license():
    """Called by the Mac app when the user enters their license key + email."""
    data = request.get_json() or {}
    license_key = data.get("license_key")
    email = data.get("email")

    if not license_key or not email:
        return jsonify({"error": "license_key and email are required"}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM licenses WHERE license_key = ? AND email = ?", (license_key, email))
    lic = c.fetchone()
    conn.close()

    if not lic:
        return jsonify({"valid": False, "reason": "Invalid license key or email"}), 404

    if not is_subscription_active(lic):
        return jsonify({"valid": False, "reason": "Subscription is no longer active. Please check your Stripe account."}), 403

    # Return success. The app should store the license_key + email locally.
    return jsonify({
        "valid": True,
        "license_key": license_key,
        "email": email,
        "signature": sign_license(license_key, email),   # optional basic offline check
        "message": "Premium activated successfully."
    })

@app.route('/validate', methods=['POST'])
def validate_license():
    """Called by the app (recommended on launch or periodically) to confirm the license is still valid."""
    data = request.get_json() or {}
    license_key = data.get("license_key")
    email = data.get("email")

    if not license_key or not email:
        return jsonify({"valid": False, "reason": "Missing license_key or email"}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM licenses WHERE license_key = ? AND email = ?", (license_key, email))
    lic = c.fetchone()
    conn.close()

    if not lic:
        return jsonify({"valid": False, "reason": "License not found"})

    if not is_subscription_active(lic):
        return jsonify({"valid": False, "reason": "Subscription is no longer active"})

    return jsonify({
        "valid": True,
        "email": email,
        "expires": (datetime.now() + timedelta(days=VALIDATION_INTERVAL_DAYS)).isoformat()
    })

# ==================== UTILITY ====================
@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

if __name__ == '__main__':
    print("Starting Beacon licensing backend...")
    missing = []
    if not STRIPE_SECRET_KEY or STRIPE_SECRET_KEY.startswith("sk_test_YOUR"):
        missing.append("STRIPE_SECRET_KEY")
    if not PREMIUM_PRICE_ID or PREMIUM_PRICE_ID.startswith("price_YOUR"):
        missing.append("PREMIUM_PRICE_ID")
    if missing:
        print("WARNING: Missing or placeholder env vars:", ", ".join(missing))
        print("Set them with: export VAR=value")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)