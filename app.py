# app.py - خادم Flask لمتجر HIBE STORE
# يوفر واجهات API للمنتجات ويخدم صفحات HTML

import json
import os
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from flask_cors import CORS  # للتجارب المحلية، يمكنك إلغاء تثبيته إذا لم تكن بحاجة

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # يسمح بطلبات من أي مصدر (للتطوير)

# مسار ملف تخزين المنتجات
PRODUCTS_FILE = 'products.json'

# تحميل المنتجات من ملف JSON أو إنشاء بيانات افتراضية
def load_products():
    if not os.path.exists(PRODUCTS_FILE):
        # بيانات افتراضية شاملة جميع التصنيفات المطلوبة
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

# ------------------ صفحات HTML الثابتة ------------------
# قراءة محتويات ملفات HTML (لتجنب مشاكل المسارات)
def get_home_html():
    try:
        with open('home.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>ملف home.html غير موجود. تأكد من وجوده في نفس مجلد app.py</h1>"

def get_man_html():
    try:
        with open('man.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>ملف man.html غير موجود. تأكد من وجوده في نفس مجلد app.py</h1>"

@app.route('/')
def home():
    return render_template_string(get_home_html())

@app.route('/home.html')
def home_page():
    return render_template_string(get_home_html())

@app.route('/man.html')
def admin_page():
    return render_template_string(get_man_html())

# ------------------ API لإدارة المنتجات ------------------
@app.route('/api/products', methods=['GET'])
def get_products():
    products = load_products()
    return jsonify(products)

@app.route('/api/products', methods=['POST'])
def add_product():
    data = request.get_json()
    if not data or 'name' not in data or 'category' not in data or 'price' not in data:
        return jsonify({'error': 'بيانات غير مكتملة'}), 400
    products = load_products()
    new_id = max([p['id'] for p in products]) + 1 if products else 1
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

# ------------------ تشغيل الخادم ------------------
if __name__ == '__main__':
    # تأكد من وجود الملفين home.html و man.html في نفس المجلد
    print("✅ خادم HIBE STORE يعمل على http://127.0.0.1:5000")
    print("📦 واجهة المتجر: http://127.0.0.1:5000/home.html")
    print("🛠️ لوحة الإدارة: http://127.0.0.1:5000/man.html")
    app.run(debug=True, host='0.0.0.0', port=5000)
