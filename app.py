# app.py - خادم Flask مع PostgreSQL لتخزين المنتجات والتصنيفات والطلبات
import json
import os
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ------------------ اتصال قاعدة البيانات ------------------
DATABASE_URL = "postgresql://hibe_store_user:mMocyX638yt9YuRvHKml3bvh6YEjp07O@dpg-d8o43g8g4nts73cajcbg-a.oregon-postgres.render.com/hibe_store"

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """إنشاء الجداول إذا لم تكن موجودة"""
    conn = get_db_connection()
    cur = conn.cursor()
    # جدول المنتجات
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price NUMERIC(10,2) NOT NULL,
            icon TEXT NOT NULL,
            image_url TEXT
        )
    """)
    # جدول التصنيفات (حفظ كقائمة بسيطة من النصوص)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY
        )
    """)
    # جدول الطلبات
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            customer_name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            notes TEXT,
            items JSONB NOT NULL,
            total NUMERIC(10,2),
            status TEXT DEFAULT 'قيد التسليم',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # إدخال التصنيفات الافتراضية إذا كان الجدول فارغاً
    cur.execute("SELECT COUNT(*) FROM categories")
    count = cur.fetchone()['count']
    if count == 0:
        default_cats = ["رجالي", "نسائي", "ولادي", "بناتي", "جزم", "شنط", "جواكت", "ملابس صيفية"]
        for cat in default_cats:
            cur.execute("INSERT INTO categories (name) VALUES (%s) ON CONFLICT DO NOTHING", (cat,))
    conn.commit()
    cur.close()
    conn.close()

# استدعاء دالة التهيئة عند بدء التشغيل
init_db()

# ------------------ دوال مساعدة للتعامل مع قاعدة البيانات ------------------
def get_all_products():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products ORDER BY id")
    products = cur.fetchall()
    cur.close()
    conn.close()
    return products

def get_product_by_id(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    product = cur.fetchone()
    cur.close()
    conn.close()
    return product

def add_product_to_db(name, category, price, icon, image_url):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO products (name, category, price, icon, image_url) VALUES (%s, %s, %s, %s, %s) RETURNING *",
        (name, category, price, icon, image_url)
    )
    new_product = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return new_product

def update_product_in_db(product_id, name, category, price, icon, image_url):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE products SET name=%s, category=%s, price=%s, icon=%s, image_url=%s WHERE id=%s RETURNING *",
        (name, category, price, icon, image_url, product_id)
    )
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return updated

def delete_product_from_db(product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
    conn.commit()
    cur.close()
    conn.close()

# ------------------ التصنيفات ------------------
def get_all_categories():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM categories ORDER BY name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [row['name'] for row in rows]

def add_category_to_db(name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO categories (name) VALUES (%s) ON CONFLICT DO NOTHING", (name,))
    conn.commit()
    cur.close()
    conn.close()

def delete_category_from_db(name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM categories WHERE name = %s", (name,))
    conn.commit()
    cur.close()
    conn.close()

# ------------------ الطلبات ------------------
def get_all_orders():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return orders

def add_order_to_db(customer_name, address, phone, notes, items, total):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (customer_name, address, phone, notes, items, total, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
        (customer_name, address, phone, notes, json.dumps(items), total, 'قيد التسليم', datetime.now())
    )
    new_order = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return new_order

def update_order_status(order_id, status):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = %s WHERE id = %s RETURNING *", (status, order_id))
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return updated

# ------------------ واجهات API ------------------
@app.route('/api/products', methods=['GET'])
def get_products():
    products = get_all_products()
    return jsonify(products)

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.get_json()
    if not data or 'name' not in data or 'category' not in data or 'price' not in data:
        return jsonify({'error': 'بيانات غير مكتملة'}), 400
    name = data['name']
    category = data['category']
    price = float(data['price'])
    icon = data.get('icon', 'bi bi-tag')
    image_url = data.get('image_url', '')
    try:
        new_product = add_product_to_db(name, category, price, icon, image_url)
        return jsonify(new_product), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.get_json()
    name = data.get('name')
    category = data.get('category')
    price = float(data.get('price'))
    icon = data.get('icon', 'bi bi-tag')
    image_url = data.get('image_url', '')
    try:
        updated = update_product_in_db(product_id, name, category, price, icon, image_url)
        if updated:
            return jsonify(updated)
        else:
            return jsonify({'error': 'المنتج غير موجود'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        delete_product_from_db(product_id)
        return jsonify({'message': 'تم حذف المنتج'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ------------------ التصنيفات ------------------
@app.route('/api/categories', methods=['GET'])
def get_categories():
    cats = get_all_categories()
    return jsonify(cats)

@app.route('/api/categories', methods=['POST'])
def add_category():
    data = request.get_json()
    new_cat = data.get('name')
    if not new_cat:
        return jsonify({'error': 'اسم التصنيف مطلوب'}), 400
    try:
        add_category_to_db(new_cat)
        return jsonify({'message': 'تمت الإضافة', 'categories': get_all_categories()}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/categories/<string:cat_name>', methods=['DELETE'])
def delete_category(cat_name):
    try:
        delete_category_from_db(cat_name)
        return jsonify({'message': 'تم الحذف', 'categories': get_all_categories()}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ------------------ الطلبات ------------------
@app.route('/api/orders', methods=['GET'])
def get_orders():
    orders = get_all_orders()
    return jsonify(orders)

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    customer_name = data.get('customerName')
    address = data.get('address')
    phone = data.get('phone')
    notes = data.get('notes', '')
    items = data.get('items', [])
    total = data.get('total', 0)
    try:
        new_order = add_order_to_db(customer_name, address, phone, notes, items, total)
        return jsonify(new_order), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/<int:order_id>', methods=['PUT'])
def update_order_status(order_id):
    data = request.get_json()
    new_status = data.get('status')
    try:
        updated = update_order_status(order_id, new_status)
        if updated:
            return jsonify(updated)
        else:
            return jsonify({'error': 'الطلب غير موجود'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ------------------ صفحات HTML ------------------
def read_html_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"<h1>الملف {filename} غير موجود. تأكد من وجوده في نفس المجلد.</h1>"

@app.route('/')
def home():
    return render_template_string(read_html_file('home.html'))

@app.route('/home.html')
def home_page():
    return render_template_string(read_html_file('home.html'))

@app.route('/man.html')
def admin_page():
    return render_template_string(read_html_file('man.html'))

if __name__ == '__main__':
    print("✅ خادم HIBE STORE (مع PostgreSQL) يعمل على http://127.0.0.1:5000")
    print("📦 واجهة المتجر: http://127.0.0.1:5000/home.html")
    print("🛠️ لوحة الإدارة: http://127.0.0.1:5000/man.html")
    app.run(debug=True, host='0.0.0.0', port=5000)
