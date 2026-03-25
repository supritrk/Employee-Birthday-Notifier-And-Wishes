# 🎂 Birthday Tracker Pro

A professional Flask web app with role-based login, employee management, and email birthday wishes.

## Quick Start

1. Install Flask:
   pip install flask

2. Run the app:
   python app.py

3. Open browser: http://localhost:5000

## Default Login
   Username: admin
   Password: admin123

## Roles
- **Admin**: Can add/remove employees, manage users, configure email settings
- **Employee**: Can view birthdays and send wishes (cannot add/remove employees)

## Features
- Secure login with sessions
- Role-based access (Admin vs Employee)
- SQLite database (no setup needed — auto-created on first run)
- Dashboard: today's birthdays + upcoming 30 days
- Send birthday wish emails
- Notify entire team about a birthday
- Admin: manage users (create/delete accounts)
- Admin: configure Gmail App Password for sending emails

## Gmail App Password Setup
1. Go to myaccount.google.com/apppasswords
2. Create a new App Password named "Birthday App"
3. Copy the 16-character password
4. In the app go to Settings and paste it there

## Files
  app.py              ← Main Flask application
  birthday.db         ← SQLite database (auto-created)
  templates/
    login.html        ← Login page
    base.html         ← Shared layout
    dashboard.html    ← Main dashboard
    employees.html    ← Employee list
    add_employee.html ← Add employee form (admin only)
    wish.html         ← Send birthday wish
    users.html        ← Manage users (admin only)
    settings.html     ← Email settings (admin only)
