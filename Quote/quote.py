from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify
import sqlite3
import random
from jinja2 import Environment
from markupsafe import Markup
import difflib
from itsdangerous import URLSafeTimedSerializer as Serializer, BadSignature, SignatureExpired
import os
import logging

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Khóa bí mật để mã hóa token
app.config['JSON_AS_ASCII'] = False

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ADMIN_PASSWORD = "1"
BACKGROUND_COLOR_FILE = os.path.join(app.instance_path, 'background_color.txt')
NAVBAR_COLOR_FILE = os.path.join(app.instance_path, 'navbar_color.txt')
DEFAULT_BACKGROUND_COLOR = '#3A4A3A'
DEFAULT_NAVBAR_COLOR = '#4A5A4A'

def nl2br(value):
    return Markup(value.replace('\n', '<br>'))

app.jinja_env.filters['nl2br'] = nl2br

def init_db():
    try:
        os.makedirs(app.instance_path, exist_ok=True)  # Ensure instance folder exists
        conn = sqlite3.connect('quotes.db')
        conn.execute('PRAGMA encoding = "UTF-8"')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS quotes 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      content TEXT NOT NULL,
                      category TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS tokens 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      token TEXT NOT NULL,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()

        # Initialize background_color.txt with default color if it doesn't exist
        if not os.path.exists(BACKGROUND_COLOR_FILE):
            try:
                with open(BACKGROUND_COLOR_FILE, 'w') as f:
                    f.write(DEFAULT_BACKGROUND_COLOR)
                logger.info(f"Created {BACKGROUND_COLOR_FILE} with default color {DEFAULT_BACKGROUND_COLOR}")
            except IOError as e:
                logger.error(f"Error creating {BACKGROUND_COLOR_FILE}: {str(e)}")
                flash(f"Không thể tạo file màu nền: {str(e)}", "error")

        # Initialize navbar_color.txt with default color if it doesn't exist
        if not os.path.exists(NAVBAR_COLOR_FILE):
            try:
                with open(NAVBAR_COLOR_FILE, 'w') as f:
                    f.write(DEFAULT_NAVBAR_COLOR)
                logger.info(f"Created {NAVBAR_COLOR_FILE} with default color {DEFAULT_NAVBAR_COLOR}")
            except IOError as e:
                logger.error(f"Error creating {NAVBAR_COLOR_FILE}: {str(e)}")
                flash(f"Không thể tạo file màu navbar: {str(e)}", "error")
    except Exception as e:
        logger.error(f"Error initializing database or color files: {str(e)}")
        flash(f"Lỗi khởi tạo cơ sở dữ liệu hoặc file màu: {str(e)}", "error")

def check_password(password):
    return password == ADMIN_PASSWORD

def generate_token(expiration=180 * 24 * 3600):  # 180 ngày
    s = Serializer(app.secret_key)
    return s.dumps({'authenticated': True})

def verify_token(token, expiration=180 * 24 * 3600):
    s = Serializer(app.secret_key)
    try:
        s.loads(token, max_age=expiration)
        conn = sqlite3.connect('quotes.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM tokens WHERE token = ?", (token,))
        exists = c.fetchone()[0] > 0
        conn.close()
        return exists
    except (BadSignature, SignatureExpired):
        logger.warning(f"Invalid or expired token: {token}")
        return False

def get_background_color():
    try:
        if not os.path.exists(BACKGROUND_COLOR_FILE):
            logger.info(f"{BACKGROUND_COLOR_FILE} does not exist, creating with default color {DEFAULT_BACKGROUND_COLOR}")
            with open(BACKGROUND_COLOR_FILE, 'w') as f:
                f.write(DEFAULT_BACKGROUND_COLOR)
        with open(BACKGROUND_COLOR_FILE, 'r') as f:
            color = f.read().strip()
            if color.startswith('#') and len(color) == 7:
                logger.debug(f"Read background color {color} from {BACKGROUND_COLOR_FILE}")
                return color
            else:
                logger.warning(f"Invalid background color {color} in {BACKGROUND_COLOR_FILE}, using default {DEFAULT_BACKGROUND_COLOR}")
                return DEFAULT_BACKGROUND_COLOR
    except IOError as e:
        logger.error(f"Error reading {BACKGROUND_COLOR_FILE}: {str(e)}")
        flash(f"Lỗi khi đọc màu nền: {str(e)}", "error")
        return DEFAULT_BACKGROUND_COLOR

def get_navbar_color():
    try:
        if not os.path.exists(NAVBAR_COLOR_FILE):
            logger.info(f"{NAVBAR_COLOR_FILE} does not exist, creating with default color {DEFAULT_NAVBAR_COLOR}")
            with open(NAVBAR_COLOR_FILE, 'w') as f:
                f.write(DEFAULT_NAVBAR_COLOR)
        with open(NAVBAR_COLOR_FILE, 'r') as f:
            color = f.read().strip()
            if color.startswith('#') and len(color) == 7:
                logger.debug(f"Read navbar color {color} from {NAVBAR_COLOR_FILE}")
                return color
            else:
                logger.warning(f"Invalid navbar color {color} in {NAVBAR_COLOR_FILE}, using default {DEFAULT_NAVBAR_COLOR}")
                return DEFAULT_NAVBAR_COLOR
    except IOError as e:
        logger.error(f"Error reading {NAVBAR_COLOR_FILE}: {str(e)}")
        flash(f"Lỗi khi đọc màu navbar: {str(e)}", "error")
        return DEFAULT_NAVBAR_COLOR

def save_background_color(color):
    try:
        with open(BACKGROUND_COLOR_FILE, 'w') as f:
            f.write(color)
        with open(BACKGROUND_COLOR_FILE, 'r') as f:
            saved_color = f.read().strip()
            if saved_color != color:
                logger.error(f"Background color {color} was not saved correctly, found {saved_color}")
                flash("Lỗi: Màu nền không được lưu chính xác!", "error")
                return False
        logger.info(f"Saved background color {color} to {BACKGROUND_COLOR_FILE}")
        return True
    except PermissionError:
        logger.error(f"Permission denied when writing to {BACKGROUND_COLOR_FILE}")
        flash("Không có quyền ghi vào file màu nền!", "error")
        return False
    except IOError as e:
        logger.error(f"Error writing to {BACKGROUND_COLOR_FILE}: {str(e)}")
        flash(f"Lỗi khi lưu màu nền: {str(e)}", "error")
        return False

def save_navbar_color(color):
    try:
        with open(NAVBAR_COLOR_FILE, 'w') as f:
            f.write(color)
        with open(NAVBAR_COLOR_FILE, 'r') as f:
            saved_color = f.read().strip()
            if saved_color != color:
                logger.error(f"Navbar color {color} was not saved correctly, found {saved_color}")
                flash("Lỗi: Màu navbar không được lưu chính xác!", "error")
                return False
        logger.info(f"Saved navbar color {color} to {NAVBAR_COLOR_FILE}")
        return True
    except PermissionError:
        logger.error(f"Permission denied when writing to {NAVBAR_COLOR_FILE}")
        flash("Không có quyền ghi vào file màu navbar!", "error")
        return False
    except IOError as e:
        logger.error(f"Error writing to {NAVBAR_COLOR_FILE}: {str(e)}")
        flash(f"Lỗi khi lưu màu navbar: {str(e)}", "error")
        return False

@app.route('/', methods=['GET', 'POST'])
def quotes():
    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')
    c = conn.cursor()

    c.execute("SELECT DISTINCT category FROM quotes")
    categories = [row[0] for row in c.fetchall()]

    quote = None
    selected_category = None

    c.execute("SELECT * FROM quotes")
    all_quotes = c.fetchall()

    if request.method == 'POST':
        if 'category' in request.form and request.form['category']:
            selected_category = request.form['category']
            c.execute("SELECT * FROM quotes WHERE category = ?", (selected_category,))
            quotes_list = c.fetchall()
            if quotes_list:
                quote = random.choice(quotes_list)
        else:
            if all_quotes:
                quote = random.choice(all_quotes)

    if not quote and all_quotes:
        quote = random.choice(all_quotes)

    conn.close()
    auth_token = request.cookies.get('auth_token')
    is_authenticated = auth_token and verify_token(auth_token)
    background_color = get_background_color()
    navbar_color = get_navbar_color()
    return render_template('quotes.html', quote=quote, categories=categories,
                           selected_category=selected_category, background_color=background_color,
                           navbar_color=navbar_color, require_password=not is_authenticated)

@app.route('/manage', methods=['GET', 'POST'])
def manage():
    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')
    c = conn.cursor()

    auth_token = request.cookies.get('auth_token')
    is_authenticated = auth_token and verify_token(auth_token)

    response = None
    if request.method == 'POST':
        password = request.form.get('password')
        if not is_authenticated and not check_password(password):
            flash("Mật khẩu không đúng!", "error")
            logger.warning("Authentication failed for manage route")
            c.execute("SELECT * FROM quotes ORDER BY content")
            quotes = c.fetchall()
            c.execute("SELECT DISTINCT category FROM quotes")
            categories = [row[0] for row in c.fetchall()]
            c.execute("SELECT category, COUNT(*) as count FROM quotes GROUP BY category")
            category_counts = c.fetchall()
            conn.close()
            background_color = get_background_color()
            navbar_color = get_navbar_color()
            return render_template('index.html', quotes=quotes, categories=categories,
                                   category_counts=category_counts, require_password=True,
                                   background_color=background_color, navbar_color=navbar_color)

        if not is_authenticated and check_password(password):
            token = generate_token()
            c.execute("INSERT INTO tokens (token) VALUES (?)", (token,))
            conn.commit()
            response = make_response(redirect(url_for('manage')))
            response.set_cookie('auth_token', token, max_age=180 * 24 * 3600, httponly=True, secure=True,
                                samesite='Strict')
            flash("Xác thực thành công! Thiết bị này sẽ không cần nhập mật khẩu trong 180 ngày.", "success")
            logger.info("Generated new authentication token for manage route")

        if 'content' in request.form and 'category' in request.form:
            content = request.form['content'].strip()
            category = request.form['category'].strip()

            c.execute("SELECT content FROM quotes")
            existing_quotes = [row[0] for row in c.fetchall()]
            for existing_content in existing_quotes:
                similarity = difflib.SequenceMatcher(None, content.lower(), existing_content.lower()).ratio()
                if similarity >= 0.8:
                    flash("Trích dẫn này quá giống (≥95%) với một trích dẫn đã tồn tại! Vui lòng nhập trích dẫn khác.",
                          "error")
                    c.execute("SELECT * FROM quotes ORDER BY content")
                    quotes = c.fetchall()
                    c.execute("SELECT DISTINCT category FROM quotes")
                    categories = [row[0] for row in c.fetchall()]
                    c.execute("SELECT category, COUNT(*) as count FROM quotes GROUP BY category")
                    category_counts = c.fetchall()
                    conn.close()
                    background_color = get_background_color()
                    navbar_color = get_navbar_color()
                    return render_template('index.html', quotes=quotes, categories=categories,
                                           category_counts=category_counts, require_password=not is_authenticated,
                                           background_color=background_color, navbar_color=navbar_color)

            c.execute("INSERT INTO quotes (content, category) VALUES (?, ?)", (content, category))
            conn.commit()
            flash("Trích dẫn đã được thêm thành công!", "success")
            logger.info(f"Added new quote: {content[:50]}... in category {category}")

    c.execute("SELECT * FROM quotes ORDER BY content")
    quotes = c.fetchall()
    c.execute("SELECT DISTINCT category FROM quotes")
    categories = [row[0] for row in c.fetchall()]
    c.execute("SELECT category, COUNT(*) as count FROM quotes GROUP BY category")
    category_counts = c.fetchall()

    conn.close()
    background_color = get_background_color()
    navbar_color = get_navbar_color()
    return response or render_template('index.html', quotes=quotes, categories=categories,
                                       category_counts=category_counts, require_password=not is_authenticated,
                                       background_color=background_color, navbar_color=navbar_color)

@app.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    auth_token = request.cookies.get('auth_token')
    is_authenticated = auth_token and verify_token(auth_token)

    response = None
    if request.method == 'POST':
        password = request.form.get('password')
        if not is_authenticated and not check_password(password):
            flash("Mật khẩu không đúng!", "error")
            logger.warning(f"Authentication failed for edit quote {id}")
            return redirect(url_for('manage'))

        if not is_authenticated and check_password(password):
            conn = sqlite3.connect('quotes.db')
            c = conn.cursor()
            token = generate_token()
            c.execute("INSERT INTO tokens (token) VALUES (?)", (token,))
            conn.commit()
            response = make_response(redirect(url_for('manage')))
            response.set_cookie('auth_token', token, max_age=180 * 24 * 3600, httponly=True, secure=True,
                                samesite='Strict')
            flash("Xác thực thành công! Thiết bị này sẽ không cần nhập mật khẩu trong 180 ngày.", "success")
            logger.info(f"Generated new authentication token for edit quote {id}")

        content = request.form['content']
        category = request.form['category']

        conn = sqlite3.connect('quotes.db')
        conn.execute('PRAGMA encoding = "UTF-8"')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM quotes WHERE id = ?", (id,))
        if c.fetchone()[0] == 0:
            flash("Trích dẫn không tồn tại!", "error")
            logger.warning(f"Quote {id} does not exist")
            conn.close()
            return response or redirect(url_for('manage'))

        c.execute("UPDATE quotes SET content = ?, category = ? WHERE id = ?", (content, category, id))
        conn.commit()
        conn.close()
        flash("Trích dẫn đã được sửa thành công!", "success")
        logger.info(f"Edited quote {id}")

    return response or redirect(url_for('manage'))

@app.route('/delete/<int:id>')
def delete(id):
    auth_token = request.cookies.get('auth_token')
    is_authenticated = auth_token and verify_token(auth_token)

    response = None
    password = request.args.get('password')
    if not is_authenticated and not check_password(password):
        flash("Mật khẩu không đúng!", "error")
        logger.warning(f"Authentication failed for delete quote {id}")
        return redirect(url_for('manage'))

    if not is_authenticated and check_password(password):
        conn = sqlite3.connect('quotes.db')
        c = conn.cursor()
        token = generate_token()
        c.execute("INSERT INTO tokens (token) VALUES (?)", (token,))
        conn.commit()
        response = make_response(redirect(url_for('manage')))
        response.set_cookie('auth_token', token, max_age=180 * 24 * 3600, httponly=True, secure=True, samesite='Strict')
        flash("Xác thực thành công! Thiết bị này sẽ không cần nhập mật khẩu trong 180 ngày.", "success")
        logger.info(f"Generated new authentication token for delete quote {id}")

    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM quotes WHERE id = ?", (id,))
    if c.fetchone()[0] == 0:
        flash("Trích dẫn không tồn tại!", "error")
        logger.warning(f"Quote {id} does not exist")
        conn.close()
        return response or redirect(url_for('manage'))

    c.execute("DELETE FROM quotes WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Trích dẫn đã được xóa thành công!", "success")
    logger.info(f"Deleted quote {id}")

    return response or redirect(url_for('manage'))

@app.route('/delete_category/<category>')
def delete_category(category):
    auth_token = request.cookies.get('auth_token')
    is_authenticated = auth_token and verify_token(auth_token)

    response = None
    password = request.args.get('password')
    if not is_authenticated and not check_password(password):
        flash("Mật khẩu không đúng!", "error")
        logger.warning(f"Authentication failed for delete category {category}")
        return redirect(url_for('manage'))

    if not is_authenticated and check_password(password):
        conn = sqlite3.connect('quotes.db')
        c = conn.cursor()
        token = generate_token()
        c.execute("INSERT INTO tokens (token) VALUES (?)", (token,))
        conn.commit()
        response = make_response(redirect(url_for('manage')))
        response.set_cookie('auth_token', token, max_age=180 * 24 * 3600, httponly=True, secure=True, samesite='Strict')
        flash("Xác thực thành công! Thiết bị này sẽ không cần nhập mật khẩu trong 180 ngày.", "success")
        logger.info(f"Generated new authentication token for delete category {category}")

    conn = sqlite3.connect('quotes.db')
    conn.execute('PRAGMA encoding = "UTF-8"')
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM quotes WHERE category = ?", (category,))
    quote_count = c.fetchone()[0]

    if quote_count > 0:
        flash(
            f"Không thể xóa nguồn '{category}' vì đang chứa {quote_count} trích dẫn. Vui lòng xóa hết trích dẫn trong nguồn này trước.",
            "error")
        logger.warning(f"Cannot delete category {category} with {quote_count} quotes")
    else:
        flash(f"Nguồn '{category}' đã được xóa thành công.", "success")
        logger.info(f"Deleted category {category}")

    conn.close()
    return response or redirect(url_for('manage'))

@app.route('/set_color', methods=['POST'])
def set_color():
    background_color = request.form.get('background_color', DEFAULT_BACKGROUND_COLOR)
    navbar_color = request.form.get('navbar_color', DEFAULT_NAVBAR_COLOR)

    # Validate hex colors
    valid = True
    if not (background_color.startswith('#') and len(background_color) == 7):
        valid = False
        flash("Màu nền trang không hợp lệ! Vui lòng chọn mã màu hex hợp lệ (ví dụ: #3A4A3A).", "error")
    if not (navbar_color.startswith('#') and len(navbar_color) == 7):
        valid = False
        flash("Màu thanh điều hướng không hợp lệ! Vui lòng chọn mã màu hex hợp lệ (ví dụ: #4A5A4A).", "error")

    if not valid:
        return jsonify({'success': False, 'message': 'Một hoặc cả hai màu không hợp lệ!'}), 400

    # Save colors
    background_success = save_background_color(background_color)
    navbar_success = save_navbar_color(navbar_color)

    if background_success and navbar_success:
        return jsonify({'success': True, 'message': 'Màu nền và màu navbar đã được thay đổi thành công!'})
    else:
        return jsonify({'success': False, 'message': 'Lỗi khi lưu một hoặc cả hai màu!'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)