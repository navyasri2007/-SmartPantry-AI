from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
app = Flask(__name__)
app.secret_key = 'supersecretkey12345changeitlater'

# === TEMPORARY HARDCODED CONFIG (for debugging) ===
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'password123'          # Empty password
app.config['MYSQL_DB'] = 'smartpantry'

mysql = MySQL(app)

print("✅ Flask app started with MySQL config:")
print("Host:", app.config['MYSQL_HOST'])
print("User:", app.config['MYSQL_USER'])
print("Password:", repr(app.config['MYSQL_PASSWORD']))  # Shows if it's really empty

# ====================== ROUTES ======================

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not email or not password:
            flash('All fields are required!', 'danger')
            return render_template('register.html')
        
        hashed_password = generate_password_hash(password)
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            if cur.fetchone():
                flash('Username or Email already exists!', 'danger')
            else:
                cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                           (username, email, hashed_password))
                mysql.connection.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            cur.close()
        except Exception as e:
            print("🔥 DB Error:", str(e))
            flash(f'Database Error: {str(e)}', 'danger')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id, username, password FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            cur.close()
            
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password!', 'danger')
        except Exception as e:
            print("Login Error:", str(e))
            flash('Login error occurred', 'danger')
    
    return render_template('login.html')

from datetime import date   # Add this import at the top

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    
    # Get all pantry items
    cur.execute("""
        SELECT id, ingredient_name, quantity, unit, expiry_date 
        FROM pantry_items 
        WHERE user_id = %s 
        ORDER BY expiry_date ASC
    """, (session['user_id'],))
    items = cur.fetchall()
    
    # Count expiring soon
    cur.execute("""
        SELECT COUNT(*) FROM pantry_items 
        WHERE user_id = %s AND expiry_date <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
    """, (session['user_id'],))
    expiring_soon = cur.fetchone()[0]
    
    cur.close()
    
    return render_template('dashboard.html', 
                         items=items, 
                         expiring_soon=expiring_soon,
                         username=session.get('username'),
                         today=date.today())
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
# ====================== PANTRY ROUTES ======================

@app.route('/pantry')
def pantry():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM pantry_items WHERE user_id = %s ORDER BY expiry_date", (session['user_id'],))
    items = cur.fetchall()
    cur.close()
    
    return render_template('pantry.html', items=items)

@app.route('/add_pantry', methods=['POST'])
def add_pantry():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    ingredient_name = request.form['ingredient_name'].strip()
    quantity = request.form['quantity']
    unit = request.form['unit']
    expiry_date = request.form['expiry_date']
    
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO pantry_items (user_id, ingredient_name, quantity, unit, expiry_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], ingredient_name, quantity, unit, expiry_date))
        mysql.connection.commit()
        cur.close()
        flash('Ingredient added successfully!', 'success')
    except Exception as e:
        flash('Error adding ingredient', 'danger')
    
    return redirect(url_for('pantry'))

@app.route('/delete_pantry/<int:item_id>')
def delete_pantry(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM pantry_items WHERE id = %s AND user_id = %s", (item_id, session['user_id']))
    mysql.connection.commit()
    cur.close()
    flash('Ingredient deleted!', 'success')
    return redirect(url_for('pantry'))


if __name__ == '__main__':
    app.run(debug=True)