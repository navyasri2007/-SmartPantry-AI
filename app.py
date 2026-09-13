from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date,timedelta

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
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')
@app.route('/shopping_list')
def shopping_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT ingredient_name FROM pantry_items WHERE user_id = %s", (session['user_id'],))
    pantry_ingredients = [row[0].lower() for row in cur.fetchall()]
    cur.close()
    
    # Common ingredients that might be missing
    common_ingredients = ['rice', 'chicken', 'tomato', 'onion', 'garlic', 'milk', 'egg', 'bread', 'potato', 'oil']
    missing = [item.title() for item in common_ingredients if item not in pantry_ingredients]
    
    return render_template('shopping_list.html', missing=missing, pantry_ingredients=pantry_ingredients)
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



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    
    # Get pantry items
    cur.execute("""
        SELECT id, ingredient_name, quantity, unit, expiry_date 
        FROM pantry_items 
        WHERE user_id = %s 
        ORDER BY expiry_date ASC
    """, (session['user_id'],))
    items = cur.fetchall()
    
    # Expiring soon count
    cur.execute("""
        SELECT COUNT(*) FROM pantry_items 
        WHERE user_id = %s AND expiry_date <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
    """, (session['user_id'],))
    expiring_soon = cur.fetchone()[0]
    
    # Status data for chart
    cur.execute("""
        SELECT 
            CASE 
                WHEN expiry_date <= DATE_ADD(CURDATE(), INTERVAL 3 DAY) THEN 'Urgent'
                WHEN expiry_date <= DATE_ADD(CURDATE(), INTERVAL 7 DAY) THEN 'Soon'
                ELSE 'Good'
            END as status, 
            COUNT(*) as count
        FROM pantry_items 
        WHERE user_id = %s 
        GROUP BY status
    """, (session['user_id'],))
    status_data = cur.fetchall()
    
    cur.close()
    
    return render_template('dashboard.html', 
                         items=items,
                         expiring_soon=expiring_soon,
                         status_data=status_data,
                         username=session.get('username'),
                         today=date.today())
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
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

import requests

from datetime import date, timedelta

@app.route('/recipes')
def recipes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT ingredient_name, expiry_date 
        FROM pantry_items 
        WHERE user_id = %s
    """, (session['user_id'],))
    pantry = cur.fetchall()  # List of (name, expiry_date)
    cur.close()
    
    user_ingredients = [row[0].lower() for row in pantry]
    today = date.today()
    
    scored_recipes = []
    
    try:
        for ing in user_ingredients[:5]:
            resp = requests.get(f"https://www.themealdb.com/api/json/v1/1/filter.php?i={ing}")
            if resp.status_code == 200:
                meals = resp.json().get('meals', [])
                for meal in meals[:8]:
                    # Smart Scoring
                    match_count = 0
                    expiry_bonus = 0
                    
                    # Count matches + expiry priority
                    for p_name, p_expiry in pantry:
                        if p_name.lower() in meal['strMeal'].lower():
                            match_count += 1
                            if p_expiry:
                                days_left = (p_expiry - today).days
                                if days_left <= 3:
                                    expiry_bonus += 35
                                elif days_left <= 7:
                                    expiry_bonus += 20
                    
                    final_score = (match_count * 25) + expiry_bonus
                    final_score = min(98, final_score)
                    
                    scored_recipes.append({
                        "id": meal['idMeal'],
                        "title": meal['strMeal'],
                        "image": meal['strMealThumb'],
                        "score": final_score,
                    })
    except Exception as e:
        print("API Error:", e)
    
    # Remove duplicates and sort by score
    unique_recipes = {r['id']: r for r in scored_recipes}
    final_recipes = sorted(list(unique_recipes.values()), key=lambda x: x['score'], reverse=True)[:12]
    
    return render_template('recipes.html', recipes=final_recipes)
@app.route('/use_recipe/<recipe_id>')
def use_recipe(recipe_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # For demo: remove some ingredients (you can expand this)
    cur = mysql.connection.cursor()
    # Example: remove common ingredients like pasta, tomato etc.
    cur.execute("""
        DELETE FROM pantry_items 
        WHERE user_id = %s 
        AND ingredient_name IN ('pasta', 'tomato', 'banana', 'milk')
        LIMIT 3
    """, (session['user_id'],))
    mysql.connection.commit()
    cur.close()
    
    flash('Recipe used successfully! Ingredients have been deducted from your pantry.', 'success')
    return redirect(url_for('dashboard'))
@app.route('/recipe/<meal_id>')
def recipe_detail(meal_id):
    try:
        response = requests.get(f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={meal_id}")
        meal = response.json()['meals'][0] if response.json().get('meals') else None
    except:
        meal = None
    
    return render_template('recipe_detail.html', meal=meal)
if __name__ == '__main__':
    app.run(debug=True)