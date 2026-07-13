import os
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect, generate_csrf
from wtforms import Form, StringField, FloatField
from wtforms.validators import DataRequired, Length, NumberRange, URL, Optional
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────
# 1. التهيئة والإعدادات
# ─────────────────────────────────────────────────────────────
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production-32chars-long')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/hibe_store'
    )
    # تكوين Connection Pooling لتحمل 1500-3000 مستخدم متزامن
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,              # اتصالات دائمة
        'max_overflow': 40,           # اتصالات إضافية عند الضغط
        'pool_timeout': 30,           # ثواني انتظار الاتصال
        'pool_recycle': 1800,         # إعادة تدوير الاتصال كل 30 دقيقة
        'pool_pre_ping': True         # التحقق من صحة الاتصال قبل الاستخدام
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-change-me')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    CACHE_TYPE = 'SimpleCache'        # قابل للترقية إلى Redis
    CACHE_DEFAULT_TIMEOUT = 300
    BCRYPT_LOG_ROUNDS = 12
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/static')
app.config.from_object(Config)

# ─────────────────────────────────────────────────────────────
# 2. الإضافات (Extensions)
# ─────────────────────────────────────────────────────────────
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
csrf = CSRFProtect(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # قابل للترقية إلى Redis
)

cache = Cache(app)

# Security Headers إجبارية
Talisman(
    app,
    force_https=False,  # اجعلها True في الإنتاج
    content_security_policy={
        'default-src': "'self'",
        'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'",
                       "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
        'style-src': ["'self'", "'unsafe-inline'",
                      "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
        'img-src': ["'self'", "data:", "https://images.unsplash.com",
                    "https://img.sanishtech.com"],
        'font-src': ["'self'", "https://fonts.gstatic.com", "https://cdn.jsdelivr.net"],
        'connect-src': "'self'"
    }
)

# ─────────────────────────────────────────────────────────────
# 3. نظام التسجيل (Logging)
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 4. نماذج قاعدة البيانات (ORM)
# ─────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False, index=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    icon = db.Column(db.String(100), default='bi bi-tag')
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.relationship('Category', backref='products')


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(500))
    phone = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text)
    items = db.Column(db.JSON, nullable=False)
    total = db.Column(db.Numeric(10, 2))
    status = db.Column(db.String(50), default='قيد التسليم')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─────────────────────────────────────────────────────────────
# 5. التحقق من المدخلات (Forms Validation)
# ─────────────────────────────────────────────────────────────
class ProductForm(Form):
    name = StringField('Name', validators=[DataRequired(), Length(max=200)])
    category = StringField('Category', validators=[DataRequired(), Length(max=100)])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0.01)])
    icon = StringField('Icon', validators=[Optional(), Length(max=100)])
    image_url = StringField('Image URL', validators=[Optional(), URL(), Length(max=500)])


class OrderForm(Form):
    customerName = StringField('Customer Name', validators=[DataRequired(), Length(max=200)])
    address = StringField('Address', validators=[Optional(), Length(max=500)])
    phone = StringField('Phone', validators=[DataRequired(), Length(min=6, max=50)])
    notes = StringField('Notes', validators=[Optional(), Length(max=1000)])


class CategoryForm(Form):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])

# ─────────────────────────────────────────────────────────────
# 6. أدوات الأمان المساعدة
# ─────────────────────────────────────────────────────────────
def admin_required(fn):
    """مصادقة JWT + صلاحية الأدمن"""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()
        if not user or not user.is_admin:
            logger.warning(f'Admin access denied for user: {current_user}')
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


@app.errorhandler(404)
def not_found(error):
    logger.warning(f'404 at {request.url}')
    return jsonify({'error': 'Resource not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f'500 error: {str(error)}', exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(429)
def ratelimit_handler(e):
    logger.warning(f'Rate limit exceeded from {request.remote_addr}')
    return jsonify({'error': 'Rate limit exceeded', 'retry_after': e.description}), 429


@app.after_request
def security_headers(response):
    """إضافة رؤوس الأمان الإضافية"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

# ─────────────────────────────────────────────────────────────
# 7. مسارات المصادقة (Auth)
# ─────────────────────────────────────────────────────────────
@app.route('/api/auth/login', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip().lower()
    password = str(data.get('password', ''))

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    access_token = create_access_token(identity=username)
    logger.info(f'User {username} logged in')
    return jsonify({'access_token': access_token, 'is_admin': user.is_admin})


@app.route('/api/auth/register', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per hour")
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get('username', '')).strip().lower()
    password = str(data.get('password', ''))

    if not username or len(password) < 8:
        return jsonify({'error': 'Invalid input. Password must be >= 8 chars.'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'User already exists'}), 409

    user = User(username=username, is_admin=False)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    logger.info(f'New user registered: {username}')
    return jsonify({'message': 'User created successfully'}), 201

# ─────────────────────────────────────────────────────────────
# 8. مسارات المنتجات (Products)
# ─────────────────────────────────────────────────────────────
@app.route('/api/products', methods=['GET'])
@cache.cached(timeout=60)
def get_products():
    try:
        products = Product.query.all()
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'category': p.category.name if p.category else None,
            'price': float(p.price),
            'icon': p.icon,
            'image_url': p.image_url
        } for p in products])
    except Exception as e:
        logger.error(f'Error fetching products: {e}')
        return jsonify({'error': 'Failed to fetch products'}), 500


@app.route('/api/products', methods=['POST'])
@csrf.exempt
@jwt_required()
@admin_required
@limiter.limit("30 per minute")
def add_product():
    data = request.get_json(silent=True) or {}
    form = ProductForm(data=data)
    if not form.validate():
        return jsonify({'error': form.errors}), 400

    try:
        cat = Category.query.filter_by(name=form.category.data).first()
        if not cat:
            cat = Category(name=form.category.data)
            db.session.add(cat)
            db.session.flush()

        product = Product(
            name=form.name.data,
            category_id=cat.id,
            price=form.price.data,
            icon=form.icon.data or 'bi bi-tag',
            image_url=form.image_url.data
        )
        db.session.add(product)
        db.session.commit()
        cache.clear()
        logger.info(f'Product added: {product.name} (ID: {product.id})')
        return jsonify({
            'id': product.id, 'name': product.name,
            'category': product.category.name, 'price': float(product.price),
            'icon': product.icon, 'image_url': product.image_url
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error adding product: {e}')
        return jsonify({'error': 'Failed to add product'}), 500


@app.route('/api/products/<int:product_id>', methods=['PUT'])
@csrf.exempt
@jwt_required()
@admin_required
@limiter.limit("30 per minute")
def update_product(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json(silent=True) or {}
    form = ProductForm(data=data)
    if not form.validate():
        return jsonify({'error': form.errors}), 400

    try:
        if form.category.data:
            cat = Category.query.filter_by(name=form.category.data).first()
            if not cat:
                cat = Category(name=form.category.data)
                db.session.add(cat)
                db.session.flush()
            product.category_id = cat.id

        product.name = form.name.data or product.name
        product.price = form.price.data if form.price.data is not None else product.price
        product.icon = form.icon.data or product.icon
        product.image_url = form.image_url.data or product.image_url

        db.session.commit()
        cache.clear()
        logger.info(f'Product updated: {product.id}')
        return jsonify({
            'id': product.id, 'name': product.name,
            'category': product.category.name, 'price': float(product.price),
            'icon': product.icon, 'image_url': product.image_url
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating product: {e}')
        return jsonify({'error': 'Failed to update product'}), 500


@app.route('/api/products/<int:product_id>', methods=['DELETE'])
@csrf.exempt
@jwt_required()
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    try:
        db.session.delete(product)
        db.session.commit()
        cache.clear()
        logger.info(f'Product deleted: {product.id}')
        return jsonify({'message': 'Product deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting product: {e}')
        return jsonify({'error': 'Failed to delete product'}), 500

# ─────────────────────────────────────────────────────────────
# 9. مسارات التصنيفات (Categories)
# ─────────────────────────────────────────────────────────────
@app.route('/api/categories', methods=['GET'])
@cache.cached(timeout=120)
def get_categories():
    try:
        cats = Category.query.all()
        return jsonify([c.name for c in cats])
    except Exception as e:
        logger.error(f'Error fetching categories: {e}')
        return jsonify({'error': 'Failed to fetch categories'}), 500


@app.route('/api/categories', methods=['POST'])
@csrf.exempt
@jwt_required()
@admin_required
@limiter.limit("30 per minute")
def add_category():
    data = request.get_json(silent=True) or {}
    form = CategoryForm(data=data)
    if not form.validate():
        return jsonify({'error': form.errors}), 400

    if Category.query.filter_by(name=form.name.data).first():
        return jsonify({'error': 'Category already exists'}), 409

    try:
        cat = Category(name=form.name.data)
        db.session.add(cat)
        db.session.commit()
        cache.clear()
        logger.info(f'Category added: {cat.name}')
        return jsonify({'message': 'Category added', 'name': cat.name}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error adding category: {e}')
        return jsonify({'error': 'Failed to add category'}), 500


@app.route('/api/categories/<string:cat_name>', methods=['DELETE'])
@csrf.exempt
@jwt_required()
@admin_required
def delete_category(cat_name):
    cat = Category.query.filter_by(name=cat_name).first_or_404()
    try:
        db.session.delete(cat)
        db.session.commit()
        cache.clear()
        logger.info(f'Category deleted: {cat.name}')
        return jsonify({'message': 'Category deleted'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting category: {e}')
        return jsonify({'error': 'Failed to delete category'}), 500

# ─────────────────────────────────────────────────────────────
# 10. مسارات الطلبات (Orders)
# ─────────────────────────────────────────────────────────────
@app.route('/api/orders', methods=['GET'])
@csrf.exempt
@jwt_required()
@admin_required
def get_orders():
    try:
        orders = Order.query.order_by(Order.id.desc()).all()
        return jsonify([{
            'id': o.id,
            'customerName': o.customer_name,
            'phone': o.phone,
            'address': o.address,
            'notes': o.notes,
            'items': o.items,
            'total': float(o.total) if o.total else 0,
            'status': o.status,
            'createdAt': o.created_at.isoformat() if o.created_at else None
        } for o in orders])
    except Exception as e:
        logger.error(f'Error fetching orders: {e}')
        return jsonify({'error': 'Failed to fetch orders'}), 500


@app.route('/api/orders', methods=['POST'])
@csrf.exempt
@limiter.limit("20 per minute")
def create_order():
    data = request.get_json(silent=True) or {}
    form = OrderForm(data=data)
    if not form.validate():
        return jsonify({'error': form.errors}), 400

    items = data.get('items', [])
    total = data.get('total', 0)

    if not isinstance(items, list):
        return jsonify({'error': 'Items must be a list'}), 400
    try:
        total = float(total)
    except (ValueError, TypeError):
        return jsonify({'error': 'Total must be a number'}), 400

    try:
        order = Order(
            customer_name=form.customerName.data,
            address=form.address.data,
            phone=form.phone.data,
            notes=form.notes.data,
            items=items,
            total=total
        )
        db.session.add(order)
        db.session.commit()
        logger.info(f'Order created: {order.id}')
        return jsonify({
            'id': order.id,
            'customerName': order.customer_name,
            'total': float(order.total) if order.total else 0,
            'status': order.status,
            'createdAt': order.created_at.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error creating order: {e}')
        return jsonify({'error': 'Failed to create order'}), 500


@app.route('/api/orders/<int:order_id>', methods=['PUT'])
@csrf.exempt
@jwt_required()
@admin_required
def update_order_status(order_id):
    data = request.get_json(silent=True) or {}
    order = Order.query.get_or_404(order_id)
    new_status = str(data.get('status', '')).strip()
    if not new_status or len(new_status) > 50:
        return jsonify({'error': 'Invalid status'}), 400

    try:
        order.status = new_status
        db.session.commit()
        logger.info(f'Order {order_id} status updated to {new_status}')
        return jsonify({'id': order.id, 'status': order.status})
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating order: {e}')
        return jsonify({'error': 'Failed to update order'}), 500

# ─────────────────────────────────────────────────────────────
# 11. مسارات الواجهة (Web Pages)
# ─────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/home.html')
def home():
    return render_template('store.html', csrf_token=generate_csrf())


@app.route('/man.html')
def admin_page():
    return render_template('admin.html', csrf_token=generate_csrf())

# ─────────────────────────────────────────────────────────────
# 12. تهيئة قاعدة البيانات
# ─────────────────────────────────────────────────────────────
def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            logger.info('Default admin created: admin / admin123 (CHANGE IMMEDIATELY!)')

if __name__ == '__main__':
    init_db()
    logger.info('HIBE STORE server starting...')
    # threaded=True يسمح بمعالجة طلبات متعددة في نفس الوقت
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
