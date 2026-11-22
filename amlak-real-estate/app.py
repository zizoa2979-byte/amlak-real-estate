import os
import io
import csv
import json
import base64
import sqlite3
from datetime import datetime
from functools import wraps
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, Response, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'amlak_pro_crm_secret_key_zizo_2026')

DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_PG = bool(DATABASE_URL and psycopg2)
SQLITE_PATH = '/tmp/amlak_v2.db' if os.environ.get('VERCEL') else 'amlak_v2.db'

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin').strip()
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'Zizo@Amlak2026').strip()
WHATSAPP_NUMBER = "201025090134"

VIEWING_SLOTS = [
    "الفترة الأولى: من 10:00 صباحاً إلى 12:00 ظهراً",
    "الفترة الثانية: من 3:00 عصراً إلى 5:00 مساءً"
]


class DBWrapper:
    def __init__(self):
        self.is_pg = USE_PG
        if self.is_pg:
            self.conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            self.conn.autocommit = True
        else:
            self.conn = sqlite3.connect(SQLITE_PATH)
            self.conn.row_factory = sqlite3.Row

    def execute(self, query, params=()):
        cur = self.conn.cursor()
        if self.is_pg:
            query = query.replace('?', '%s')
        cur.execute(query, params)
        return cur

    def fetchall(self, query, params=()):
        cur = self.execute(query, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def fetchone(self, query, params=()):
        cur = self.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None

    def commit(self):
        if not self.is_pg:
            self.conn.commit()

    def close(self):
        self.conn.close()


def init_db():
    db = DBWrapper()
    id_col = "SERIAL PRIMARY KEY" if db.is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"

    db.execute(f"""
        CREATE TABLE IF NOT EXISTS properties (
            id {id_col},
            code TEXT,
            title TEXT NOT NULL,
            purpose TEXT NOT NULL,
            prop_type TEXT NOT NULL,
            city TEXT NOT NULL,
            district TEXT NOT NULL,
            price REAL NOT NULL,
            area REAL NOT NULL,
            rooms INTEGER DEFAULT 3,
            bathrooms INTEGER DEFAULT 2,
            floor_num TEXT DEFAULT 'الأول',
            finishing TEXT DEFAULT 'سوبر لوكس',
            status TEXT DEFAULT 'متاح',
            image_url TEXT,
            extra_images TEXT DEFAULT '[]',
            description TEXT,
            features TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    db.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            id {id_col},
            full_name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            favorites TEXT DEFAULT '[]',
            created_at TEXT
        )
    """)

    db.execute(f"""
        CREATE TABLE IF NOT EXISTS inquiries (
            id {id_col},
            property_id INTEGER,
            property_code TEXT,
            property_title TEXT,
            user_id INTEGER,
            client_name TEXT NOT NULL,
            client_phone TEXT NOT NULL,
            preferred_date TEXT,
            notes TEXT,
            status TEXT DEFAULT 'قيد المراجعة',
            priority_num INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    count_row = db.fetchone("SELECT COUNT(*) as cnt FROM properties")
    if count_row and count_row['cnt'] == 0:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        sample_props = [
            (
                "AML-101", "شقة فاخرة بإطلالة مفتوحة على المشاية السفلية", "بيع", "شقة",
                "المنصورة", "المشاية السفلية", 3850000, 185, 3, 2, "الخامس", "الترا سوبر لوكس", "متاح",
                "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=900",
                json.dumps([
                    "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=900",
                    "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=900"
                ]),
                "شقة سكنية راقية بتشطيب حديث بالكامل، ريسبشن 3 قطع، غرف نوم واسعة، أمن وحراسة 24 ساعة وأسانسير حديث.",
                "أسانسير, أمن 24 ساعة, غاز طبيعي, عداد كهرباء, إطلالة مفتوحة", now_str
            ),
            (
                "AML-102", "فيلا مستقلة بحديقة خاصة وحمام سباحة", "بيع", "فيلا",
                "المنصورة", "حي الجامعة", 8900000, 420, 5, 4, "أرضي + أول + روف", "سوبر لوكس", "متاح",
                "https://images.unsplash.com/photo-1613977257363-707ba9348227?w=900",
                json.dumps([
                    "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=900",
                    "https://images.unsplash.com/photo-1600047509807-ba8f99d2cdde?w=900"
                ]),
                "فيلا مستقلة بتصميم معماري عصري، حديقة خاصة 150 متر، جراج خاص لسيارتين، موقع هادئ وقريب من كافة الخدمات.",
                "حديقة خاصة, حمام سباحة, جراج خاص, كاميرات مراقبة", now_str
            ),
            (
                "AML-103", "شقة مودرن مفروشة بالكامل للإيجار", "إيجار", "شقة",
                "المنصورة", "توريل الجديدة", 14000, 150, 3, 2, "الثالث", "فرش فندقي", "متاح",
                "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=900",
                json.dumps([
                    "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=900"
                ]),
                "شقة مكيفة بالكامل بأثاث عصري وأجهزة كهربائية حديثة، مناسبة للعائلات أو المغتربين والطلاب.",
                "مكيفة بالكامل, فرش حديث, واي فاي, أسانسير", now_str
            ),
            (
                "AML-104", "مقر إداري / عيادة طبية بموقع حيوي", "إيجار", "مقر إداري",
                "نبروه", "شارع الجمهورية الرئيسي", 9500, 120, 3, 1, "الثاني", "سوبر لوكس", "متاح",
                "https://images.unsplash.com/photo-1497366216548-37526070297c?w=900",
                json.dumps([
                    "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=900"
                ]),
                "مقر إداري أو عيادة جاهزة للتشغيل الفوري على الشارع الرئيسي مباشرة بواجهة زجاجية مميزة.",
                "واجهة رئيسية, يصلح عيادة أو شركة, عداد تجاري", now_str
            )
        ]
        for p in sample_props:
            db.execute("""
                INSERT INTO properties
                (code, title, purpose, prop_type, city, district, price, area, rooms, bathrooms, floor_num, finishing, status, image_url, extra_images, description, features, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, p)

    db.commit()
    db.close()


try:
    init_db()
except Exception as e:
    print("DB Init Note:", e)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


def parse_property_images(prop):
    imgs = []
    if prop.get('image_url'):
        imgs.append(prop['image_url'])
    try:
        extras = json.loads(prop.get('extra_images') or '[]')
        if isinstance(extras, list):
            for u in extras:
                if u and u not in imgs:
                    imgs.append(u)
    except Exception:
        pass
    if not imgs:
        imgs.append("https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=900")
    prop['all_images'] = imgs
    prop['price_per_meter'] = int(round(prop['price'] / prop['area'])) if prop.get('area') else 0
    return prop


@app.route('/')
def index():
    db = DBWrapper()
    purpose = request.args.get('purpose', '').strip()
    prop_type = request.args.get('prop_type', '').strip()
    city = request.args.get('city', '').strip()
    max_price = request.args.get('max_price', '').strip()
    search_q = request.args.get('q', '').strip()

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
    if max_price:
        try:
            query += " AND price <= ?"
            params.append(float(max_price))
        except ValueError:
            pass
    if search_q:
        query += " AND (title LIKE ? OR district LIKE ? OR code LIKE ? OR description LIKE ?)"
        like_q = f"%{search_q}%"
        params.extend([like_q, like_q, like_q, like_q])

    query += " ORDER BY id DESC"
    properties = [parse_property_images(p) for p in db.fetchall(query, tuple(params))]

    inq_counts = {}
    for row in db.fetchall("SELECT property_id, COUNT(*) as cnt FROM inquiries WHERE status != 'مرفوض' GROUP BY property_id"):
        inq_counts[row['property_id']] = row['cnt']

    current_user = None
    user_favorites = []
    if session.get('user_id'):
        current_user = db.fetchone("SELECT * FROM users WHERE id = ?", (session['user_id'],))
        if current_user:
            try:
                user_favorites = json.loads(current_user.get('favorites') or '[]')
            except Exception:
                user_favorites = []

    db.close()
    return render_template(
        'index.html',
        properties=properties,
        inq_counts=inq_counts,
        current_user=current_user,
        user_favorites=user_favorites,
        whatsapp_number=WHATSAPP_NUMBER,
        viewing_slots=VIEWING_SLOTS,
        today_date=datetime.now().strftime("%Y-%m-%d"),
        db_mode="PostgreSQL (Supabase)" if USE_PG else "Local SQLite",
        filters={
            'purpose': purpose,
            'prop_type': prop_type,
            'city': city,
            'max_price': max_price,
            'q': search_q
        }
    )


@app.route('/api/booked-slots')
def api_booked_slots():
    date_str = request.args.get('date', '').strip()
    if not date_str:
        return jsonify({'booked_slots': [], 'is_full': False})

    db = DBWrapper()
    rows = db.fetchall(
        "SELECT preferred_date FROM inquiries WHERE preferred_date LIKE ? AND status != 'مرفوض'",
        (f"{date_str}%",)
    )
    db.close()

    booked_slots = []
    for r in rows:
        pd = r.get('preferred_date') or ''
        for slot in VIEWING_SLOTS:
            if slot in pd and slot not in booked_slots:
                booked_slots.append(slot)

    is_full = len(booked_slots) >= len(VIEWING_SLOTS) or len(rows) >= 2
    return jsonify({'booked_slots': booked_slots, 'is_full': is_full})


@app.route('/register', methods=['POST'])
def register():
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '').strip()

    if not full_name or not phone or len(password) < 4:
        flash("يرجى إدخال الاسم ورقم الموبايل وكلمة مرور لا تقل عن 4 أحرف.", "danger")
        return redirect(url_for('index'))

    db = DBWrapper()
    existing = db.fetchone("SELECT id FROM users WHERE phone = ?", (phone,))
    if existing:
        db.close()
        flash("رقم الموبايل مسجل بالفعل! يمكنك تسجيل الدخول مباشرة.", "warning")
        return redirect(url_for('index'))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    db.execute(
        "INSERT INTO users (full_name, phone, password_hash, favorites, created_at) VALUES (?, ?, ?, '[]', ?)",
        (full_name, phone, generate_password_hash(password), now_str)
    )
    db.commit()
    user = db.fetchone("SELECT * FROM users WHERE phone = ?", (phone,))
    db.close()

    session['user_id'] = user['id']
    session['user_name'] = user['full_name']
    flash(f"أهلاً بك يا {full_name}! تم إنشاء حسابك بنجاح.", "success")
    return redirect(url_for('my_account'))


@app.route('/login', methods=['POST'])
def client_login():
    phone = request.form.get('phone', '').strip()
    password = request.form.get('password', '').strip()

    db = DBWrapper()
    user = db.fetchone("SELECT * FROM users WHERE phone = ?", (phone,))
    db.close()

    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['user_name'] = user['full_name']
        flash(f"مرحباً بعودتك يا {user['full_name']}!", "success")
        return redirect(url_for('my_account'))

    flash("رقم الموبايل أو كلمة المرور غير صحيحة.", "danger")
    return redirect(url_for('index'))


@app.route('/logout')
def client_logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    flash("تم تسجيل الخروج من حسابك.", "info")
    return redirect(url_for('index'))


@app.route('/toggle-favorite/<int:prop_id>', methods=['POST'])
def toggle_favorite(prop_id):
    if not session.get('user_id'):
        flash("سجل دخولك أولاً لحفظ العقارات في قائمة المفضلة.", "warning")
        return redirect(url_for('index'))

    db = DBWrapper()
    user = db.fetchone("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    if user:
        try:
            favs = json.loads(user.get('favorites') or '[]')
        except Exception:
            favs = []
        if prop_id in favs:
            favs.remove(prop_id)
            msg = "تمت إزالة العقار من المفضلة."
        else:
            favs.append(prop_id)
            msg = "تم حفظ العقار في قائمة المفضلة ❤️"
        db.execute("UPDATE users SET favorites = ? WHERE id = ?", (json.dumps(favs), user['id']))
        db.commit()
        flash(msg, "success")
    db.close()
    return redirect(request.referrer or url_for('index'))


@app.route('/my-account')
def my_account():
    if not session.get('user_id'):
        flash("يرجى تسجيل الدخول للوصول إلى حسابك.", "warning")
        return redirect(url_for('index'))

    db = DBWrapper()
    user = db.fetchone("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    if not user:
        db.close()
        session.pop('user_id', None)
        return redirect(url_for('index'))

    my_inquiries = db.fetchall(
        "SELECT * FROM inquiries WHERE user_id = ? OR client_phone = ? ORDER BY id DESC",
        (user['id'], user['phone'])
    )

    try:
        fav_ids = json.loads(user.get('favorites') or '[]')
    except Exception:
        fav_ids = []

    fav_properties = []
    if fav_ids:
        placeholders = ",".join(["?"] * len(fav_ids))
        raw_favs = db.fetchall(f"SELECT * FROM properties WHERE id IN ({placeholders})", tuple(fav_ids))
        fav_properties = [parse_property_images(p) for p in raw_favs]

    db.close()
    return render_template(
        'account.html',
        user=user,
        inquiries=my_inquiries,
        fav_properties=fav_properties,
        whatsapp_number=WHATSAPP_NUMBER
    )


@app.route('/book-viewing', methods=['POST'])
def book_viewing():
    prop_id = request.form.get('property_id')
    client_name = request.form.get('client_name', '').strip()
    client_phone = request.form.get('client_phone', '').strip()
    booking_day = request.form.get('booking_day', '').strip()
    booking_slot = request.form.get('booking_slot', '').strip()
    notes = request.form.get('notes', '').strip()

    if not booking_day or not booking_slot:
        flash("يرجى اختيار اليوم والفترة المناسبة للمعاينة.", "danger")
        return redirect(url_for('index'))

    db = DBWrapper()
    prop = db.fetchone("SELECT * FROM properties WHERE id = ?", (prop_id,))
    if not prop:
        db.close()
        flash("العقار المطلوب غير موجود.", "danger")
        return redirect(url_for('index'))

    if prop['status'] == 'مباع':
        db.close()
        flash("عذراً، هذا العقار تم بيعه بالفعل.", "danger")
        return redirect(url_for('index'))

    day_bookings = db.fetchall(
        "SELECT preferred_date FROM inquiries WHERE preferred_date LIKE ? AND status != 'مرفوض'",
        (f"{booking_day}%",)
    )
    if len(day_bookings) >= 2:
        db.close()
        flash("عذراً، هذا اليوم مكتمل الحجوزات (الحد الأقصى فترتان في اليوم). يرجى اختيار يوم آخر.", "warning")
        return redirect(url_for('index'))

    for b in day_bookings:
        if booking_slot in (b.get('preferred_date') or ''):
            db.close()
            flash("عذراً، هذه الفترة تم حجزها للتو. يرجى اختيار الفترة الأخرى أو يوم آخر.", "warning")
            return redirect(url_for('index'))

    preferred_date = f"{booking_day} | {booking_slot}"

    existing_cnt = db.fetchone(
        "SELECT COUNT(*) as cnt FROM inquiries WHERE property_id = ? AND status != 'مرفوض'",
        (prop['id'],)
    )
    priority_num = (existing_cnt['cnt'] if existing_cnt else 0) + 1

    user_id = session.get('user_id')
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    initial_status = "قائمة انتظار (محجوز مبدئياً)" if prop['status'] == 'محجوز مبدئياً' else "قيد المراجعة"

    db.execute("""
        INSERT INTO inquiries
        (property_id, property_code, property_title, user_id, client_name, client_phone, preferred_date, notes, status, priority_num, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        prop['id'], prop.get('code', f"AML-{prop['id']}"), prop['title'],
        user_id, client_name, client_phone, preferred_date, notes,
        initial_status, priority_num, now_str
    ))
    db.commit()
    db.close()

    wa_msg = (
        f"السلام عليكم منصة أملاك العقارية 🏢\n"
        f"قمت بتسجيل طلب معاينة جديد:\n"
        f"• كود العقار: {prop.get('code', prop['id'])}\n"
        f"• العقار: {prop['title']}\n"
        f"• الاسم: {client_name}\n"
        f"• الهاتف: {client_phone}\n"
        f"• الموعد المختار: {preferred_date}\n"
        f"• ترتيب الأولوية: #{priority_num}"
    )
    wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={quote(wa_msg)}"
    session['last_wa_link'] = wa_link
    session['last_priority'] = priority_num
    flash(f"تم تسجيل طلبك بنجاح لموعد ({preferred_date})! ترتيبك في الأولوية هو #{priority_num}.", "success")
    return redirect(url_for('index', booked='1'))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        error = "بيانات الدخول غير صحيحة! تم رفض الوصول."

    return render_template('admin.html', login_mode=True, error=error)


@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))


def get_admin_data():
    db = DBWrapper()
    properties = [parse_property_images(p) for p in db.fetchall("SELECT * FROM properties ORDER BY id DESC")]
    inquiries = db.fetchall("SELECT * FROM inquiries ORDER BY id DESC")
    users = db.fetchall("SELECT id, full_name, phone, created_at FROM users ORDER BY id DESC")

    stats = {
        'total_props': len(properties),
        'available_props': sum(1 for p in properties if p['status'] == 'متاح'),
        'reserved_props': sum(1 for p in properties if p['status'] == 'محجوز مبدئياً'),
        'sold_props': sum(1 for p in properties if p['status'] in ('مباع', 'مؤجر')),
        'pending_inquiries': sum(1 for i in inquiries if 'قيد المراجعة' in i['status'] or 'انتظار' in i['status']),
        'total_users': len(users)
    }
    db.close()
    return properties, inquiries, users, stats


@app.route('/admin')
@admin_required
def admin_dashboard():
    properties, inquiries, users, stats = get_admin_data()
    return render_template(
        'admin.html',
        login_mode=False,
        properties=properties,
        inquiries=inquiries,
        users=users,
        stats=stats,
        whatsapp_number=WHATSAPP_NUMBER,
        db_mode="PostgreSQL (Supabase)" if USE_PG else "SQLite المؤقت (تحذير: تأكد من ربط Supabase)"
    )


@app.route('/admin/live-data')
@admin_required
def admin_live_data():
    _, inquiries, users, stats = get_admin_data()
    return jsonify({
        'stats': stats,
        'inquiries': inquiries,
        'users': users
    })


def image_file_to_data_uri(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    raw = file_storage.read()
    if not raw:
        return None
    mime = file_storage.mimetype or 'image/jpeg'
    b64 = base64.b64encode(raw).decode('utf-8')
    return f"data:{mime};base64,{b64}"


@app.route('/admin/add-property', methods=['POST'])
@admin_required
def add_property():
    title = request.form.get('title', '').strip()
    purpose = request.form.get('purpose', 'بيع').strip()
    prop_type = request.form.get('prop_type', 'شقة').strip()
    city = request.form.get('city', '').strip()
    district = request.form.get('district', '').strip()
    price = float(request.form.get('price') or 0)
    area = float(request.form.get('area') or 0)
    rooms = int(request.form.get('rooms') or 3)
    bathrooms = int(request.form.get('bathrooms') or 2)
    floor_num = request.form.get('floor_num', 'الأول').strip()
    finishing = request.form.get('finishing', 'سوبر لوكس').strip()
    description = request.form.get('description', '').strip()
    features = request.form.get('features', '').strip()

    uploaded_imgs = []
    for f in request.files.getlist('image_files'):
        uri = image_file_to_data_uri(f)
        if uri:
            uploaded_imgs.append(uri)

    url_lines = [u.strip() for u in request.form.get('image_urls', '').splitlines() if u.strip()]
    all_imgs = uploaded_imgs + url_lines

    main_img = all_imgs[0] if all_imgs else "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=900"
    extra_imgs = all_imgs[1:] if len(all_imgs) > 1 else []

    db = DBWrapper()
    last = db.fetchone("SELECT MAX(id) as max_id FROM properties")
    next_num = (last['max_id'] or 100) + 101
    code = f"AML-{next_num}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    db.execute("""
        INSERT INTO properties
        (code, title, purpose, prop_type, city, district, price, area, rooms, bathrooms, floor_num, finishing, status, image_url, extra_images, description, features, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'متاح', ?, ?, ?, ?, ?)
    """, (
        code, title, purpose, prop_type, city, district, price, area,
        rooms, bathrooms, floor_num, finishing, main_img,
        json.dumps(extra_imgs), description, features, now_str
    ))
    db.commit()
    db.close()
    flash(f"تم نشر العقار ({code}) بنجاح مع {len(all_imgs) or 1} صورة!", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/property-status/<int:prop_id>', methods=['POST'])
@admin_required
def update_property_status(prop_id):
    new_status = request.form.get('status', 'متاح').strip()
    db = DBWrapper()
    db.execute("UPDATE properties SET status = ? WHERE id = ?", (new_status, prop_id))
    db.commit()
    db.close()
    flash(f"تم تحديث حالة العقار إلى: {new_status}", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete-property/<int:prop_id>', methods=['POST'])
@admin_required
def delete_property(prop_id):
    db = DBWrapper()
    db.execute("DELETE FROM inquiries WHERE property_id = ?", (prop_id,))
    db.execute("DELETE FROM properties WHERE id = ?", (prop_id,))
    db.commit()
    db.close()
    flash("تم حذف العقار نهائياً.", "info")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/inquiry-action/<int:inq_id>', methods=['POST'])
@admin_required
def inquiry_action(inq_id):
    action = request.form.get('action', '')
    db = DBWrapper()
    inq = db.fetchone("SELECT * FROM inquiries WHERE id = ?", (inq_id,))
    if not inq:
        db.close()
        return redirect(url_for('admin_dashboard'))

    raw_phone = ''.join(filter(str.isdigit, inq['client_phone']))
    if raw_phone.startswith('01'):
        wa_client_phone = '2' + raw_phone
    elif raw_phone.startswith('20'):
        wa_client_phone = raw_phone
    else:
        wa_client_phone = '20' + raw_phone

    if action == 'approve':
        db.execute("UPDATE inquiries SET status = 'تمت الموافقة' WHERE id = ?", (inq_id,))
        db.execute("UPDATE properties SET status = 'محجوز مبدئياً' WHERE id = ? AND status = 'متاح'", (inq['property_id'],))
        db.commit()
        db.close()
        chosen_slot = inq.get('preferred_date') or 'الموعد المسجل'
        msg = (
            f"أهلاً أستاذ/ة {inq['client_name']} 👋\n"
            f"مع حضرتك إدارة *منصة أملاك العقارية*.\n"
            f"يسعدنا إبلاغك بـ *الموافقة على طلب المعاينة* الخاص بالعقار:\n"
            f"• كود العقار: {inq['property_code']}\n"
            f"• العقار: {inq['property_title']}\n"
            f"• الموعد المحجوز: {chosen_slot}\n"
            f"• ترتيب أولويتك: #{inq['priority_num']}\n"
            f"سيتم التواصل معك قبل الميعاد لتأكيد التفاصيل وتنسيق المعاينة."
        )
        return redirect(f"https://wa.me/{wa_client_phone}?text={quote(msg)}")

    elif action == 'reject':
        db.execute("UPDATE inquiries SET status = 'مرفوض' WHERE id = ?", (inq_id,))
        db.commit()
        db.close()
        msg = (
            f"أهلاً أستاذ/ة {inq['client_name']} 👋\n"
            f"مع حضرتك إدارة *منصة أملاك العقارية*.\n"
            f"نعتذر لحضرتك بخصوص طلب معاينة العقار ({inq['property_code']} - {inq['property_title']}) نظراً لأسبقية الحجز أو التفاوض الجاري حالياً، وسنوافيك بأقرب عقار مشابه فور توفره."
        )
        return redirect(f"https://wa.me/{wa_client_phone}?text={quote(msg)}")

    elif action == 'delete':
        db.execute("DELETE FROM inquiries WHERE id = ?", (inq_id,))
        db.commit()
        db.close()
        flash("تم حذف الطلب.", "info")
        return redirect(url_for('admin_dashboard'))

    db.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/export/<string:target>')
@admin_required
def export_excel_csv(target):
    db = DBWrapper()
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)

    if target == 'properties':
        writer.writerow(['ID', 'الكود', 'العنوان', 'الغرض', 'النوع', 'المدينة', 'الحي', 'السعر', 'المساحة', 'الغرف', 'الحمامات', 'التشطيب', 'الحالة', 'تاريخ الإضافة'])
        for r in db.fetchall("SELECT * FROM properties ORDER BY id DESC"):
            writer.writerow([r['id'], r['code'], r['title'], r['purpose'], r['prop_type'], r['city'], r['district'], r['price'], r['area'], r['rooms'], r['bathrooms'], r['finishing'], r['status'], r['created_at']])
        filename = f"amlak_properties_{datetime.now().strftime('%Y%m%d')}.csv"

    elif target == 'inquiries':
        writer.writerow(['ID', 'الأولوية', 'كود العقار', 'اسم العقار', 'اسم العميل', 'رقم الهاتف', 'الموعد المفضل', 'حالة الطلب', 'ملاحظات', 'وقت التسجيل'])
        for r in db.fetchall("SELECT * FROM inquiries ORDER BY id DESC"):
            writer.writerow([r['id'], f"#{r['priority_num']}", r['property_code'], r['property_title'], r['client_name'], f"\t{r['client_phone']}", r['preferred_date'], r['status'], r['notes'], f"\t{r['created_at']}"])
        filename = f"amlak_inquiries_{datetime.now().strftime('%Y%m%d')}.csv"

    elif target == 'users':
        writer.writerow(['ID', 'اسم العميل', 'رقم الهاتف', 'تاريخ التسجيل'])
        for r in db.fetchall("SELECT id, full_name, phone, created_at FROM users ORDER BY id DESC"):
            writer.writerow([r['id'], r['full_name'], f"\t{r['phone']}", f"\t{r['created_at']}"])
        filename = f"amlak_clients_{datetime.now().strftime('%Y%m%d')}.csv"
    else:
        db.close()
        return redirect(url_for('admin_dashboard'))

    db.close()
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


if __name__ == '__main__':
    app.run(debug=True)