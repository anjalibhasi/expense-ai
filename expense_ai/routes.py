import sqlite3
from functools import wraps

from flask import render_template, request, jsonify, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from .ai import ai_predict
from .database import get_db, get_setting


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


def register_routes(app):
    @app.route('/', methods=['GET', 'POST'])
    @login_required
    def home():
        conn = get_db()

        if request.method == 'POST':
            if request.form.get('set_budget'):
                budget_value = float(request.form.get('budget', 10000))
                uid = session.get('user_id')
                composite = f'user:{uid}:monthly_budget'
                conn.execute(
                    'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
                    (composite, str(budget_value))
                )
                conn.commit()
                conn.close()
                return redirect('/')

            date = request.form['date']
            desc = request.form['desc']
            amount = float(request.form['amount'])
            category, confidence = ai_predict(desc, app.model, app.vectorizer)
            uid = session.get('user_id')
            conn.execute(
                'INSERT INTO expenses (date, desc, amount, category, user_id) VALUES (?, ?, ?, ?, ?)',
                (date, desc, amount, category, uid)
            )
            conn.commit()

        selected_month = request.args.get('month', 'all')
        uid = session.get('user_id')
        if selected_month == 'all':
            expenses = conn.execute(
                'SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC',
                (uid,)
            ).fetchall()
        else:
            expenses = conn.execute(
                "SELECT * FROM expenses WHERE user_id = ? AND strftime('%Y-%m', date) = ? ORDER BY date DESC",
                (uid, selected_month)
            ).fetchall()

        user_budget = get_setting(conn, 'monthly_budget', 10000, uid)
        chart_data = conn.execute(
            "SELECT category, SUM(amount) FROM expenses WHERE user_id = ? AND strftime('%Y', date) = strftime('%Y', 'now') GROUP BY category",
            (uid,)
        ).fetchall()
        monthly_data = conn.execute(
            "SELECT strftime('%Y-%m', date) as month, SUM(amount) FROM expenses WHERE user_id = ? GROUP BY month ORDER BY month",
            (uid,)
        ).fetchall()
        months = conn.execute(
            "SELECT DISTINCT strftime('%Y-%m', date) FROM expenses WHERE user_id = ? ORDER BY date DESC",
            (uid,)
        ).fetchall()
        today_total = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date = date('now')",
            (uid,)
        ).fetchone()[0] or 0
        month_total = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')",
            (uid,)
        ).fetchone()[0] or 0
        year_total = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = ? AND strftime('%Y', date) = strftime('%Y', 'now')",
            (uid,)
        ).fetchone()[0] or 0
        year_budget = user_budget * 12
        budget_alert = month_total > user_budget
        year_budget_alert = year_total > year_budget
        conn.close()

        user = None
        if 'user_id' in session:
            user = {'username': session.get('username'), 'email': session.get('email')}

        return render_template(
            'index.html',
            expenses=expenses,
            chart_data=chart_data,
            monthly_data=monthly_data,
            months=months,
            selected_month=selected_month,
            today_total=today_total,
            month_total=month_total,
            year_total=year_total,
            year_budget=year_budget,
            budget=user_budget,
            budget_alert=budget_alert,
            year_budget_alert=year_budget_alert,
            user=user,
        )

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        conn = get_db()
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
                    conn.execute(
                        'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                        (username, email, hashed),
                    )
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

        conn = get_db()
        error = None
        if request.method == 'POST':
            identifier = request.form.get('identifier', '').strip()
            password = request.form.get('password', '')

            if not identifier or not password:
                error = 'Enter both username/email and password.'
            else:
                user = conn.execute(
                    'SELECT id, username, email, password FROM users WHERE username = ? OR email = ?',
                    (identifier, identifier),
                ).fetchone()
                if user and check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['email'] = user['email']
                    conn.close()
                    return redirect(url_for('home'))
                error = 'Invalid login credentials.'

        conn.close()
        return render_template('login.html', error=error)

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        if 'user_id' in session:
            return redirect(url_for('home'))

        conn = get_db()
        error = None
        message = None
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            if not email:
                error = 'Enter your registered email address.'
            elif '@' not in email:
                error = 'Please enter a valid email address.'
            else:
                user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
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
        conn = get_db()
        uid = session.get('user_id')
        conn.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (id, uid))
        conn.commit()
        conn.close()
        return redirect('/')

    @app.route('/predict', methods=['POST'])
    @login_required
    def predict():
        desc = request.json['desc']
        category, confidence = ai_predict(desc, app.model, app.vectorizer)
        return jsonify({'category': category, 'confidence': confidence})

    @app.route('/monthly')
    @login_required
    def monthly_view():
        conn = get_db()
        uid = session.get('user_id')
        user_budget = get_setting(conn, 'monthly_budget', 10000, uid)
        monthly_breakdown = conn.execute(
            """
            SELECT strftime('%Y-%m', date) as month, category, SUM(amount) as total
            FROM expenses WHERE user_id = ? GROUP BY month, category ORDER BY month DESC, total DESC
            """,
            (uid,),
        ).fetchall()
        monthly_totals = conn.execute(
            "SELECT strftime('%Y-%m', date) as month, SUM(amount) FROM expenses WHERE user_id = ? GROUP BY month ORDER BY month DESC",
            (uid,),
        ).fetchall()
        conn.close()
        user = {'username': session.get('username'), 'email': session.get('email')}
        return render_template(
            'monthly.html',
            monthly_breakdown=monthly_breakdown,
            monthly_totals=monthly_totals,
            budget=user_budget,
            user=user,
        )

    return app
