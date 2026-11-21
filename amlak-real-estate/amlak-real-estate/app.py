import os
import base64
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

app = Flask(__name__)
app.secret_key = 'amlak_real_estate_secret_key_zizo'

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_PG = bool(DATABASE_URL and psycopg2)
SQLITE_PATH = '/tmp/amlak.db' if os.environ.get('VERCEL') else 'amlak.db'

ADMIN_USER = "admin"
ADMIN_PASS = "123456"

class DBWrapper:
    def __init__(self):
        if USE_PG:
            self.conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            self.is_pg = True
        else:
            self.conn = sqlite3.connect(SQLITE_PATH)
            self.conn.row_factory = sqlite3.Row
            self.is_pg = False

    def execute(self, query, params=()):
        if self.is_pg:
            query = query.replace('?', '%s')
        cur = self.conn.cursor()
        cur.execute(query, params)
        return cur

    def executemany(self, query, seq_params):
        if self.is_pg:
            query = query.replace('?', '%s')
        cur = self.conn.cursor()
        cur.executemany(query, seq_params)
        return cur

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()

def init_db():
    with DBWrapper() as db:
        if db.is_pg:
            db.execute('''
                CREATE TABLE IF NOT EXISTS properties (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    prop_type TEXT NOT NULL,
                    city TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    area INTEGER NOT NULL,
                    bedrooms INTEGER NOT NULL,
                    bathrooms INTEGER NOT NULL,
                    image_url TEXT NOT NULL,
                    badge TEXT DEFAULT 'مميز',
                    status TEXT DEFAULT 'متاح',
                    description TEXT,
                    created_at TEXT
                )
            ''')
            db.execute('''
                CREATE TABLE IF NOT EXISTS inquiries (
                    id SERIAL PRIMARY KEY,
                    property_title TEXT,
                    client_name TEXT NOT NULL,
                    client_phone TEXT NOT NULL,
                    visit_date TEXT,
                    notes TEXT,
                    created_at TEXT
                )
            ''')
        else:
            db.execute('''
                CREATE TABLE IF NOT EXISTS properties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    prop_type TEXT NOT NULL,
                    city TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    area INTEGER NOT NULL,
                    bedrooms INTEGER NOT NULL,
                    bathrooms INTEGER NOT NULL,
                    image_url TEXT NOT NULL,
                    badge TEXT DEFAULT 'مميز',
                    status TEXT DEFAULT 'متاح',
                    description TEXT,
                    created_at TEXT
                )
            ''')
            db.execute('''
                CREATE TABLE IF NOT EXISTS inquiries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    property_title TEXT,
                    client_name TEXT NOT NULL,
                    client_phone TEXT NOT NULL,
                    visit_date TEXT,
                    notes TEXT,
                    created_at TEXT
                )
            ''')

        row = db.execute('SELECT COUNT(*) AS cnt FROM properties').fetchone()
        count = row['cnt'] if isinstance(row, dict) else row[0]

        if count == 0:
            sample_properties = [
                (
                    "فيلا مودرن مستقلة بمسبح خاص وحديقة",
                    "للبيع", "فيلا", "الرياض - حي الملقا", 4500000, 520, 5, 6,
                    "https://images.unsplash.com/photo-1613490493576-7fde63acd811?auto=format&fit=crop&w=900&q=80",
                    "حصري", "متاح",
                    "تصميم معماري فاخر بواجهات زجاجية بانورامية، تكييف مركزي مخفي، مصعد داخلي، ومجلس خارجي مطل على المسبح.",
                    "2026-11-20"
                ),
                (
                    "شقة فندقية بإطلالة بانورامية على النيل",
                    "للبيع", "شقة", "القاهرة الجديدة - التجمع الخامس", 8200000, 240, 3, 3,
                    "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?auto=format&fit=crop&w=900&q=80",
                    "مميز", "متاح",
                    "تشطيب ألترا سوبر لوكس بأجود الخامات المستوردة، أمن وحراسة 24 ساعة، ونادي صحي خاص للسكان.",
                    "2026-11-20"
                ),
                (
                    "بنتهاوس فاخر مع روف وتراس واسع",
                    "للإيجار", "دوبلكس", "دبي - داون تاون", 280000, 340, 4, 4,
                    "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?auto=format&fit=crop&w=900&q=80",
                    "مميز", "متاح",
                    "إطلالة مباشرة على أفق المدينة، مطبخ مجهز بالكامل بأحدث الأجهزة الذكية، وموقفين للسيارات.",
                    "2026-11-21"
                ),
                (
                    "قصر مصغر بتصميم كلاسيكي حديث",
                    "للبيع", "فيلا", "الشيخ زايد - بيفرلي هيلز", 14500000, 750, 6, 7,
                    "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=900&q=80",
                    "حصري", "متاح",
                    "موقع استراتيجي على ناصية شارعين، حديقة مزروعة بالكامل، جناح ضيوف مستقل، وغرفة سينما منزلية.",
                    "2026-11-21"
                ),
                (
                    "مقر إداري ذكي للشركات الكبرى",
                    "للإيجار", "مكتب إداري", "جدة - طريق الملك", 195000, 290, 6, 3,
                    "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=900&q=80",
                    "جديد", "متاح",
                    "مقسم إلى قاعات اجتماعات زجاجية ومكاتب تنفيذية مع نظام دخول ذكي بالبصمة وإنترنت فائق السرعة.",
                    "2026-11-21"
                ),
                (
                    "شقة عصرية قريبة من جميع الخدمات",
                    "للبيع", "شقة", "المنصورة - حي الجامعة", 3400000, 175, 3, 2,
                    "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?auto=format&fit=crop&w=900&q=80",
                    "جديد", "مباع",
                    "واجهة بحرية غير مجروحة، عدادات كاملة، ومدخل فندقي رخامي مع مصعدين حديثين.",
                    "2026-11-22"
                )
            ]
            db.executemany('''
                INSERT INTO properties (
                    title, purpose, prop_type, city, price, area, bedrooms, bathrooms,
                    image_url, badge, status, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', sample_properties)

try:
    init_db()
except Exception as e:
    print("DB Init warning:", e)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    init_db()
    purpose = request.args.get('purpose', '')
    prop_type = request.args.get('prop_type', '')
    city = request.args.get('city', '')
    max_price = request.args.get('max_price', '')

    query = "SELECT * FROM properties WHERE 1=1"
    params = []

    if purpose:
        query += " AND purpose = ?"
        params.append(purpose)
    if prop_type:
        query += " AND prop_type = ?"
        params.append(prop_type)
    if city:
        query += " AND city LIKE ?"
        params.append(f"%{city}%")
    if max_price and max_price.isdigit():
        query += " AND price <= ?"
        params.append(int(max_price))

    query += " ORDER BY id DESC"

    with DBWrapper() as db:
        properties = db.execute(query, params).fetchall()
        r1 = db.execute("SELECT COUNT(*) AS cnt FROM properties").fetchone()
        r2 = db.execute("SELECT COUNT(*) AS cnt FROM properties WHERE status = 'متاح'").fetchone()
        total_props = r1['cnt'] if isinstance(r1, dict) else r1[0]
        available_props = r2['cnt'] if isinstance(r2, dict) else r2[0]

    return render_template(
        'index.html',
        properties=properties,
        total_props=total_props,
        available_props=available_props,
        filters={'purpose': purpose, 'prop_type': prop_type, 'city': city, 'max_price': max_price}
    )

@app.route('/inquire', methods=['POST'])
def inquire():
    with DBWrapper() as db:
        db.execute('''
            INSERT INTO inquiries (property_title, client_name, client_phone, visit_date, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            request.form.get('property_title'),
            request.form.get('client_name'),
            request.form.get('client_phone'),
            request.form.get('visit_date'),
            request.form.get('notes'),
            datetime.now().strftime('%Y-%m-%d %H:%M')
        ))
    return redirect(url_for('index', booked=1))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        error = "بيانات الدخول غير صحيحة"
    return render_template('admin.html', login_mode=True, error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_dashboard():
    init_db()
    with DBWrapper() as db:
        properties = db.execute("SELECT * FROM properties ORDER BY id DESC").fetchall()
        inquiries = db.execute("SELECT * FROM inquiries ORDER BY id DESC").fetchall()
    return render_template('admin.html', login_mode=False, properties=properties, inquiries=inquiries)

@app.route('/admin/add', methods=['POST'])
@admin_required
def admin_add():
    img = "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=900&q=80"
    
    uploaded_file = request.files.get('image_file')
    if uploaded_file and uploaded_file.filename:
        mime_type = uploaded_file.mimetype or 'image/jpeg'
        encoded = base64.b64encode(uploaded_file.read()).decode('utf-8')
        img = f"data:{mime_type};base64,{encoded}"
    elif request.form.get('image_url'):
        img = request.form.get('image_url')

    with DBWrapper() as db:
        db.execute('''
            INSERT INTO properties (
                title, purpose, prop_type, city, price, area, bedrooms, bathrooms,
                image_url, badge, status, description, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'متاح', ?, ?)
        ''', (
            request.form.get('title'),
            request.form.get('purpose'),
            request.form.get('prop_type'),
            request.form.get('city'),
            int(request.form.get('price', 0)),
            int(request.form.get('area', 0)),
            int(request.form.get('bedrooms', 1)),
            int(request.form.get('bathrooms', 1)),
            img,
            request.form.get('badge', 'جديد'),
            request.form.get('description'),
            datetime.now().strftime('%Y-%m-%d')
        ))
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/status/<int:prop_id>/<new_status>', methods=['POST'])
@admin_required
def change_status(prop_id, new_status):
    with DBWrapper() as db:
        db.execute("UPDATE properties SET status = ? WHERE id = ?", (new_status, prop_id))
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<int:prop_id>', methods=['POST'])
@admin_required
def delete_property(prop_id):
    with DBWrapper() as db:
        db.execute("DELETE FROM properties WHERE id = ?", (prop_id,))
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)