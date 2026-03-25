from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
import smtplib
import hashlib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "birthday_pro_secret_2024")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            first TEXT NOT NULL,
            last TEXT NOT NULL,
            email TEXT NOT NULL,
            birthday TEXT NOT NULL,
            department TEXT NOT NULL,
            added_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    # Default admin user: admin / admin123
    pw = hash_pw("admin123")
    cur.execute(
        "INSERT INTO users (username, password, role) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING",
        ("admin", pw, "admin")
    )
    conn.commit()
    cur.close()
    conn.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ── Helpers ───────────────────────────────────────────────────────────────────

def days_until_birthday(bday_str):
    today = date.today()
    bday = datetime.strptime(bday_str, "%Y-%m-%d").date()
    this_year = bday.replace(year=today.year)
    if this_year < today:
        this_year = this_year.replace(year=today.year + 1)
    return (this_year - today).days

def fmt_date(bday_str):
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    p = bday_str.split("-")
    return f"{months[int(p[1])-1]} {int(p[2])}"

def get_config(key, default=""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key=%s", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["value"] if row else default

def set_config(key, value):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        (key, value)
    )
    conn.commit()
    cur.close()
    conn.close()

def send_email(to_email, to_name, subject, body):
    sender = get_config("email")
    password = get_config("password")
    smtp_host = get_config("smtp_host", "smtp.gmail.com")
    smtp_port = int(get_config("smtp_port", "587"))
    if not sender or not password:
        raise Exception("Email not configured. Go to Settings.")
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls()
        s.login(sender, password)
        s.sendmail(sender, to_email, msg.as_string())

# ── Auth decorators ───────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (username, hash_pw(password))
        )
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees ORDER BY birthday")
    employees = [dict(e) for e in cur.fetchall()]
    cur.close()
    conn.close()
    for e in employees:
        e["days_left"] = days_until_birthday(e["birthday"])
        e["birthday_display"] = fmt_date(e["birthday"])
    today_bdays = [e for e in employees if e["days_left"] == 0]
    upcoming = sorted([e for e in employees if 0 < e["days_left"] <= 30], key=lambda x: x["days_left"])
    return render_template("dashboard.html",
        employees=employees, today_bdays=today_bdays,
        upcoming=upcoming, total=len(employees))

# ── Employee management (admin only) ─────────────────────────────────────────

@app.route("/employees")
@login_required
def employees():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees ORDER BY first, last")
    emps = [dict(e) for e in cur.fetchall()]
    cur.close()
    conn.close()
    for e in emps:
        e["days_left"] = days_until_birthday(e["birthday"])
        e["birthday_display"] = fmt_date(e["birthday"])
    return render_template("employees.html", employees=emps)

@app.route("/add-employee", methods=["GET", "POST"])
@admin_required
def add_employee():
    if request.method == "POST":
        first = request.form["first"].strip()
        last = request.form["last"].strip()
        email = request.form["email"].strip()
        birthday = request.form["birthday"]
        department = request.form["department"].strip()
        if not all([first, last, email, birthday, department]):
            flash("All fields are required.", "danger")
            return render_template("add_employee.html")
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO employees (first,last,email,birthday,department,added_by) VALUES (%s,%s,%s,%s,%s,%s)",
            (first, last, email, birthday, department, session["username"])
        )
        conn.commit()
        cur.close()
        conn.close()
        flash(f"{first} {last} added successfully!", "success")
        return redirect(url_for("employees"))
    return render_template("add_employee.html")

@app.route("/delete-employee/<int:emp_id>")
@admin_required
def delete_employee(emp_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM employees WHERE id=%s", (emp_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Employee removed.", "info")
    return redirect(url_for("employees"))

# ── Wish / Notify ─────────────────────────────────────────────────────────────

@app.route("/wish/<int:emp_id>", methods=["GET", "POST"])
@login_required
def send_wish(emp_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees WHERE id=%s", (emp_id,))
    emp = cur.fetchone()
    cur.close()
    conn.close()
    if not emp:
        flash("Employee not found.", "danger")
        return redirect(url_for("dashboard"))
    emp = dict(emp)
    if request.method == "POST":
        message = request.form["message"]
        try:
            send_email(emp["email"], emp["first"],
                       f"Happy Birthday, {emp['first']}! 🎂", message)
            flash(f"Birthday wish sent to {emp['first']} {emp['last']}!", "success")
            return redirect(url_for("dashboard"))
        except Exception as ex:
            flash(f"Failed to send email: {str(ex)}", "danger")
    default_msg = (
        f"Hi {emp['first']},\n\n"
        f"Wishing you a very Happy Birthday! 🎂\n\n"
        f"Hope your day is filled with joy and wonderful moments.\n\n"
        f"Warm regards,\nThe Team"
    )
    return render_template("wish.html", emp=emp, default_msg=default_msg)

@app.route("/notify-team", methods=["POST"])
@login_required
def notify_team():
    data = request.get_json()
    emp_id = data.get("emp_id")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM employees WHERE id=%s", (emp_id,))
    birthday_person = cur.fetchone()
    cur.execute("SELECT * FROM employees WHERE id!=%s", (emp_id,))
    all_employees = cur.fetchall()
    cur.execute("SELECT * FROM users")
    all_users = cur.fetchall()
    cur.close()
    conn.close()
    if not birthday_person:
        return jsonify({"success": False, "error": "Employee not found"})
    bp = dict(birthday_person)
    sent, errors = 0, []
    notified_emails = set()
    for emp in all_employees:
        if emp["email"] in notified_emails:
            continue
        try:
            body = (f"Hi {emp['first']},\n\n"
                    f"Today is {bp['first']} {bp['last']}'s birthday! 🎂\n"
                    f"Send them a quick wish at: {bp['email']}\n\n"
                    f"Sent by: {session['username']}\n— Birthday Tracker")
            send_email(emp["email"], emp["first"],
                       f"🎂 Today is {bp['first']}'s Birthday!", body)
            notified_emails.add(emp["email"])
            sent += 1
        except Exception as ex:
            errors.append(str(ex))
    if errors and sent == 0:
        return jsonify({"success": False, "error": errors[0]})
    return jsonify({"success": True, "sent": sent})

# ── User management (admin only) ──────────────────────────────────────────────

@app.route("/users")
@admin_required
def manage_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role, created_at FROM users ORDER BY role, username")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("users.html", users=users)

@app.route("/add-user", methods=["POST"])
@admin_required
def add_user():
    username = request.form["username"].strip()
    password = request.form["password"].strip()
    role = request.form["role"]
    if not username or not password:
        flash("Username and password are required.", "danger")
        return redirect(url_for("manage_users"))
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username,password,role) VALUES (%s,%s,%s)",
                     (username, hash_pw(password), role))
        conn.commit()
        flash(f"User '{username}' created as {role}.", "success")
    except psycopg2.IntegrityError:
        conn.rollback()
        flash(f"Username '{username}' already exists.", "danger")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("manage_users"))

@app.route("/delete-user/<int:user_id>")
@admin_required
def delete_user(user_id):
    if user_id == session["user_id"]:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("manage_users"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("User deleted.", "info")
    return redirect(url_for("manage_users"))

# ── Settings (admin only) ─────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        set_config("email", request.form["email"].strip())
        set_config("password", request.form["password"].strip())
        set_config("smtp_host", request.form.get("smtp_host", "smtp.gmail.com").strip())
        set_config("smtp_port", request.form.get("smtp_port", "587").strip())
        flash("Settings saved!", "success")
        return redirect(url_for("settings"))
    config = {
        "email": get_config("email"),
        "password": get_config("password"),
        "smtp_host": get_config("smtp_host", "smtp.gmail.com"),
        "smtp_port": get_config("smtp_port", "587"),
    }
    return render_template("settings.html", config=config)

# ── Start ─────────────────────────────────────────────────────────────────────

with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n🎂  Birthday Tracker Pro is running!")
    print(f"   Open: http://localhost:{port}")
    print("   Admin login → username: admin  |  password: admin123\n")
    app.run(host="0.0.0.0", port=port, debug=False)
