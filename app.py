# app.py - خادم Flask لمتجر HIBE STORE مع إدارة الطلبات والدردشة والتصنيفات
import json
import os
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ------------------ المنتجات ------------------
PRODUCTS_FILE = 'products.json'

def load_products():
    if not os.path.exists(PRODUCTS_FILE):
        default_products = [
            {"id": 1, "name": "قميص رجالي كلاسيك", "category": "رجالي", "price": 99, "icon": "bi bi-shirt"},
            {"id": 2, "name": "فستان كتان أنيق", "category": "نسائي", "price": 149, "icon": "bi bi-gender-female"},
            {"id": 3, "name": "طقم ولادي رياضي", "category": "ولادي", "price": 79, "icon": "bi bi-emoji-smile"},
            {"id": 4, "name": "تنورة بناتي مكشكشة", "category": "بناتي", "price": 89, "icon": "bi bi-suit-heart"},
            {"id": 5, "name": "حذاء رياضي جلد", "category": "جزم", "price": 199, "icon": "bi bi-shoes"},
            {"id": 6, "name": "حقيبة ظهر جلدية", "category": "شنط", "price": 129, "icon": "bi bi-bag"},
            {"id": 7, "name": "جاكيت جينز ثقيل", "category": "جواكت", "price": 189, "icon": "bi bi-vest"},
            {"id": 8, "name": "تيشيرت صيفي قطني", "category": "ملابس صيفية", "price": 59, "icon": "bi bi-sun"},
            {"id": 9, "name": "بنطلون كارجو عسكري", "category": "رجالي", "price": 119, "icon": "bi bi-bag-plus"},
            {"id": 10, "name": "بلوزة شيفون شفاف", "category": "نسائي", "price": 109, "icon": "bi bi-flower1"},
            {"id": 11, "name": "حذاء ولادي خفيف", "category": "جزم", "price": 99, "icon": "bi bi-emoji-smile"},
            {"id": 12, "name": "شنطة كتف سهرة", "category": "شنط", "price": 159, "icon": "bi bi-gem"},
            {"id": 13, "name": "جاكيت بومبر واقي", "category": "جواكت", "price": 229, "icon": "bi bi-thermometer-snow"},
            {"id": 14, "name": "فستان صيفي طويل", "category": "ملابس صيفية", "price": 139, "icon": "bi bi-brightness-alt-high"},
            {"id": 15, "name": "بدلة بناتي كتان", "category": "بناتي", "price": 129, "icon": "bi bi-asterisk"},
            {"id": 16, "name": "طقم ولادي شتوي", "category": "ولادي", "price": 99, "icon": "bi bi-snow2"}
        ]
        save_products(default_products)
        return default_products
    with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_products(products):
    with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

@app.route('/api/products', methods=['GET'])
def get_products():
    return jsonify(load_products())

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.get_json()
    if not data or 'name' not in data or 'category' not in data or 'price' not in data:
        return jsonify({'error': 'بيانات غير مكتملة'}), 400
    products = load_products()
    new_id = max([p['id'] for p in products], default=0) + 1
    new_product = {
        'id': new_id,
        'name': data['name'],
        'category': data['category'],
        'price': float(data['price']),
        'icon': data.get('icon', 'bi bi-tag')
    }
    products.append(new_product)
    save_products(products)
    return jsonify(new_product), 201

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.get_json()
    products = load_products()
    for p in products:
        if p['id'] == product_id:
            p['name'] = data.get('name', p['name'])
            p['category'] = data.get('category', p['category'])
            p['price'] = float(data.get('price', p['price']))
            p['icon'] = data.get('icon', p['icon'])
            save_products(products)
            return jsonify(p)
    return jsonify({'error': 'المنتج غير موجود'}), 404

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    products = load_products()
    new_products = [p for p in products if p['id'] != product_id]
    if len(new_products) == len(products):
        return jsonify({'error': 'المنتج غير موجود'}), 404
    save_products(new_products)
    return jsonify({'message': 'تم حذف المنتج'}), 200

# ------------------ إدارة التصنيفات ------------------
CATEGORIES_FILE = 'categories.json'

def load_categories():
    if not os.path.exists(CATEGORIES_FILE):
        default_cats = ["رجالي", "نسائي", "ولادي", "بناتي", "جزم", "شنط", "جواكت", "ملابس صيفية"]
        save_categories(default_cats)
        return default_cats
    with open(CATEGORIES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_categories(categories):
    with open(CATEGORIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

@app.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify(load_categories())

@app.route('/api/categories', methods=['POST'])
def add_category():
    data = request.get_json()
    new_cat = data.get('name')
    if not new_cat:
        return jsonify({'error': 'اسم التصنيف مطلوب'}), 400
    cats = load_categories()
    if new_cat in cats:
        return jsonify({'error': 'التصنيف موجود بالفعل'}), 400
    cats.append(new_cat)
    save_categories(cats)
    return jsonify({'message': 'تمت الإضافة', 'categories': cats}), 201

@app.route('/api/categories/<string:cat_name>', methods=['DELETE'])
def delete_category(cat_name):
    cats = load_categories()
    if cat_name not in cats:
        return jsonify({'error': 'التصنيف غير موجود'}), 404
    cats.remove(cat_name)
    save_categories(cats)
    return jsonify({'message': 'تم الحذف', 'categories': cats})

# ------------------ إدارة الطلبات ------------------
ORDERS_FILE = 'orders.json'

def load_orders():
    if not os.path.exists(ORDERS_FILE):
        return []
    with open(ORDERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_orders(orders):
    with open(ORDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

@app.route('/api/orders', methods=['GET'])
def get_orders():
    return jsonify(load_orders())

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    orders = load_orders()
    new_id = max([o['id'] for o in orders], default=0) + 1
    new_order = {
        'id': new_id,
        'customerName': data.get('customerName'),
        'address': data.get('address'),
        'phone': data.get('phone'),
        'notes': data.get('notes', ''),
        'items': data.get('items', []),
        'total': data.get('total', 0),
        'status': 'قيد التسليم',
        'createdAt': datetime.now().isoformat()
    }
    orders.append(new_order)
    save_orders(orders)
    return jsonify(new_order), 201

@app.route('/api/orders/<int:order_id>', methods=['PUT'])
def update_order_status(order_id):
    data = request.get_json()
    new_status = data.get('status')
    orders = load_orders()
    for order in orders:
        if order['id'] == order_id:
            order['status'] = new_status
            save_orders(orders)
            return jsonify(order)
    return jsonify({'error': 'الطلب غير موجود'}), 404

# ------------------ إدارة الرسائل (الدردشة) ------------------
MESSAGES_FILE = 'messages.json'

def load_messages():
    if not os.path.exists(MESSAGES_FILE):
        return []
    with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_messages(messages):
    with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

@app.route('/api/messages', methods=['GET'])
def get_messages():
    return jsonify(load_messages())

@app.route('/api/messages', methods=['POST'])
def send_message():
    data = request.get_json()
    messages = load_messages()
    messages.append(data)
    save_messages(messages)
    return jsonify({'message': 'تم الإرسال'}), 201

@app.route('/api/messages/clear', methods=['DELETE'])
def clear_messages():
    save_messages([])
    return jsonify({'message': 'تم مسح المحادثة'}), 200

# ------------------ صفحات HTML ------------------
def read_html_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"<h1>الملف {filename} غير موجود</h1>"

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
    print("✅ خادم HIBE STORE يعمل على http://127.0.0.1:5000")
    print("📦 واجهة المتجر: http://127.0.0.1:5000/home.html")
    print("🛠️ لوحة الإدارة: http://127.0.0.1:5000/man.html")
    app.run(debug=True, host='0.0.0.0', port=5000)
