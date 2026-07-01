from flask import Flask, render_template, request, jsonify, redirect, session, url_for
import sqlite3
import pickle
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'replace_with_a_secure_random_key'
model = pickle.load(open('model.pkl', 'rb'))
vectorizer = pickle.load(open('vectorizer.pkl', 'rb'))
BUDGET = 10000


def init_tables():
    conn = sqlite3.connect('expenses.db')
    conn.execute("CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, date, desc, amount, category)")
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, email TEXT UNIQUE, password TEXT)")
    conn.close()

init_tables()


def ensure_column(table, column, definition):
    conn = sqlite3.connect('expenses.db')
    cur = conn.execute("PRAGMA table_info(%s)" % table)
    cols = [r[1] for r in cur.fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")
        conn.commit()
    conn.close()

# Ensure per-user columns exist for multi-user isolation
ensure_column('expenses', 'user_id', 'user_id INTEGER')
ensure_column('settings', 'user_id', 'user_id INTEGER')


def ai_predict(desc):
    if not desc or not desc.strip():
        return "Other", 0
    X = vectorizer.transform([desc])
    return model.predict(X)[0], round(model.predict_proba(X).max() * 100)


def get_setting(conn, key, default, user_id=None):
    # Prefer a user-scoped key stored as 'user:{id}:{key}' to avoid changing table primary keys
    if user_id is not None:
        composite = f'user:{user_id}:{key}'
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (composite,)).fetchone()
        if row:
            try:
                return float(row[0])
            except ValueError:
                return default
    # fallback to global key
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        try:
            return float(row[0])
        except ValueError:
            return default
    return default


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view

@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    conn = sqlite3.connect('expenses.db')

    if request.method == 'POST':
        if request.form.get('set_budget'):
            budget_value = float(request.form.get('budget', BUDGET))
            uid = session.get('user_id')
            composite = f'user:{uid}:monthly_budget'
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (composite, str(budget_value)))
            conn.commit()
            return redirect('/')

        date = request.form['date']
        desc = request.form['desc']
        amount = float(request.form['amount'])
        category, conf = ai_predict(desc)
        uid = session.get('user_id')
        conn.execute("INSERT INTO expenses (date, desc, amount, category, user_id) VALUES (?,?,?,?,?)", (date, desc, amount, category, uid))
        conn.commit()

    selected_month = request.args.get('month', 'all')
    uid = session.get('user_id')
    if selected_month == 'all':
        expenses = conn.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC", (uid,)).fetchall()
    else:
        expenses = conn.execute("SELECT * FROM expenses WHERE user_id = ? AND strftime('%Y-%m', date) =? ORDER BY date DESC", (uid, selected_month)).fetchall()

    user_budget = get_setting(conn, 'monthly_budget', BUDGET, uid)
    chart_data = conn.execute(
        "SELECT category, SUM(amount) FROM expenses WHERE user_id = ? AND strftime('%Y', date) = strftime('%Y', 'now') GROUP BY category",
        (uid,)
    ).fetchall()
    monthly_data = conn.execute("SELECT strftime('%Y-%m', date) as month, SUM(amount) FROM expenses WHERE user_id = ? GROUP BY month ORDER BY month", (uid,)).fetchall()
    months = conn.execute("SELECT DISTINCT strftime('%Y-%m', date) FROM expenses WHERE user_id = ? ORDER BY date DESC", (uid,)).fetchall()
    today_total = conn.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date = date('now')", (uid,)).fetchone()[0] or 0
    month_total = conn.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')", (uid,)).fetchone()[0] or 0
    year_total = conn.execute("SELECT SUM(amount) FROM expenses WHERE user_id = ? AND strftime('%Y', date) = strftime('%Y', 'now')", (uid,)).fetchone()[0] or 0
    year_budget = user_budget * 12
    budget_alert = month_total > user_budget
    year_budget_alert = year_total > year_budget

    conn.close()
    user = None
    if 'user_id' in session:
        user = {'username': session.get('username'), 'email': session.get('email')}
    return render_template('index.html', expenses=expenses, chart_data=chart_data, monthly_data=monthly_data,
                           months=months, selected_month=selected_month, today_total=today_total,
                           month_total=month_total, year_total=year_total, year_budget=year_budget,
                           budget=user_budget, budget_alert=budget_alert, year_budget_alert=year_budget_alert,
                           user=user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    conn = sqlite3.connect('expenses.db')
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or not email or not password or not confirm_password:
            error = 'All fields are required.'
        elif '@' not in email:
            error = 'Please enter a valid email address.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        else:
            try:
                hashed = generate_password_hash(password)
                conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                             (username, email, hashed))
                conn.commit()
                conn.close()
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                error = 'Username or email already exists.'

    conn.close()
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
    conn = sqlite3.connect('expenses.db')
    error = None
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')

        if not identifier or not password:
            error = 'Enter both username/email and password.'
        else:
            user = conn.execute(
                "SELECT id, username, email, password FROM users WHERE username = ? OR email = ?",
                (identifier, identifier)
            ).fetchone()
            if user and check_password_hash(user[3], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['email'] = user[2]
                conn.close()
                return redirect(url_for('home'))
            error = 'Invalid login credentials.'

    conn.close()
    return render_template('login.html', error=error)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('home'))
    conn = sqlite3.connect('expenses.db')
    error = None
    message = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            error = 'Enter your registered email address.'
        elif '@' not in email:
            error = 'Please enter a valid email address.'
        else:
            user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if user:
                message = 'If this email is registered, a password reset link has been sent.'
            else:
                error = 'No account found with that email address.'

    conn.close()
    return render_template('forgot_password.html', error=error, message=message)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    conn = sqlite3.connect('expenses.db')
    uid = session.get('user_id')
    conn.execute("DELETE FROM expenses WHERE id =? AND user_id = ?", (id, uid))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    desc = request.json['desc']
    category, confidence = ai_predict(desc)
    return jsonify({'category': category, 'confidence': confidence})

@app.route('/monthly')
@login_required
def monthly_view():
    conn = sqlite3.connect('expenses.db')
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    uid = session.get('user_id')
    user_budget = get_setting(conn, 'monthly_budget', BUDGET, uid)
    monthly_breakdown = conn.execute("""
        SELECT strftime('%Y-%m', date) as month, category, SUM(amount) as total
        FROM expenses WHERE user_id = ? GROUP BY month, category ORDER BY month DESC, total DESC
    """, (uid,)).fetchall()
    monthly_totals = conn.execute("""
        SELECT strftime('%Y-%m', date) as month, SUM(amount)
        FROM expenses WHERE user_id = ? GROUP BY month ORDER BY month DESC
    """, (uid,)).fetchall()
    conn.close()
    user = {'username': session.get('username'), 'email': session.get('email')}
    return render_template('monthly.html', monthly_breakdown=monthly_breakdown, monthly_totals=monthly_totals, budget=user_budget, user=user)

if __name__ == '__main__':
    app.run(debug=True)