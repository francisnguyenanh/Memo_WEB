import base64

from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import bcrypt
import os
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import uuid
import logging
from datetime import date, datetime
from datetime import datetime, timedelta  # Added timedelta
from uuid import uuid4  # Added uuid4
from base64 import b64encode
import json
from base64 import b64encode
from wand.image import Image
import io
import threading
import unicodedata
import sqlite3
import random
from markupsafe import Markup
import difflib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///memo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Diary app setup
diary_app = Flask(__name__)
diary_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diary.db'
diary_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db_diary = SQLAlchemy()
db_diary.init_app(diary_app)

# Quote app setup
quote_app = Flask(__name__)
quote_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quotes.db'
quote_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db_quote = SQLAlchemy()
db_quote.init_app(quote_app)


login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# User model
class User(UserMixin):
    def __init__(self):
        self.id = 'default'

# Category model
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    user_id = db.Column(db.String(80), nullable=False)
    color = db.Column(db.String(7), nullable=True)  # HEX color, e.g., #FF0000

# Note model
# Trong class Note
class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(80), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    share_id = db.Column(db.String(36), nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    images = db.Column(db.Text, nullable=True)  # Lưu JSON chứa danh sách ảnh (base64)
    category = db.relationship('Category', backref='notes')


class Diary(db_diary.Model):
    id = db_diary.Column(db_diary.Integer, primary_key=True)
    title = db_diary.Column(db_diary.String(100), nullable=False)
    content = db_diary.Column(db_diary.Text, nullable=False)
    date = db_diary.Column(db_diary.DateTime, nullable=False, default=datetime.utcnow)
    color = db_diary.Column(db_diary.String(7), nullable=False)

class Slogan(db_diary.Model):
    id = db_diary.Column(db_diary.Integer, primary_key=True)
    text = db_diary.Column(db_diary.String(200), nullable=False)

# Quote Category model
class QuoteCategory(db_quote.Model):
    id = db_quote.Column(db_quote.Integer, primary_key=True)
    name = db_quote.Column(db_quote.String(100), nullable=False, unique=True)
    quotes = db_quote.relationship('Quote', backref='category', lazy=True)

class Quote(db_quote.Model):
    id = db_quote.Column(db_quote.Integer, primary_key=True)
    content = db_quote.Column(db_quote.Text, nullable=False)
    category_id = db_quote.Column(db_quote.Integer, db_quote.ForeignKey('quote_category.id'), nullable=False)
    
# Khởi tạo DB Diary và slogan mặc định nếu chưa có
with diary_app.app_context():
    db_diary.create_all()
    if not Slogan.query.first():
        default_slogan = Slogan(text="Write your story, live your journey.")
        db_diary.session.add(default_slogan)
        db_diary.session.commit()

with quote_app.app_context():
    db_quote.create_all()
    # Thêm category mẫu nếu chưa có
    if not QuoteCategory.query.first():
        db_quote.session.add(QuoteCategory(name="General"))
        db_quote.session.commit()

# Initialize database and user.txt
with app.app_context():
    db.create_all()
    # Add default categories if not exist
    for name, color in [('Work', '#FF9999'), ('Personal', '#99FF99'), ('Ideas', '#9999FF')]:
        if not Category.query.filter_by(name=name, user_id='default').first():
            db.session.add(Category(name=name, user_id='default', color=color))
    db.session.commit()
    # Initialize user.txt with default password '1234' if not exist
    if not os.path.exists('user.txt'):
        default_password = '1234'
        hashed = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt())
        with open('user.txt', 'w') as f:
            f.write(hashed.decode('utf-8'))
            
def get_user_info():
    try:
        with open('userinfor.txt', 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
            birthday = None
            name = None
            for line in lines:
                if line.startswith('Birthday:'):
                    birthday = line.replace('Birthday:', '').strip().replace('/', '-')
                elif line.startswith('Name:'):
                    name = line.replace('Name:', '').strip()
            return name or 'Unknown', birthday
    except Exception:
        return 'Unknown', None


def nl2br(value):
    return Markup(value.replace('\n', '<br>'))

app.jinja_env.filters['nl2br'] = nl2br
quote_app.jinja_env.filters['nl2br'] = nl2br

    
@app.route('/set_theme', methods=['POST'])
def set_theme():
    theme = request.json.get('theme')
    if theme:
        session['theme'] = theme
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'No theme provided'}), 400

    
@login_manager.user_loader
def load_user(user_id):
    return User() if user_id == 'default' else None

# Verify password
def verify_password(password):
    if not os.path.exists('user.txt'):
        return False
    with open('user.txt', 'r') as f:
        hash = f.read().strip()
        return bcrypt.checkpw(password.encode('utf-8'), hash.encode('utf-8'))



# Register font for Vietnamese support
try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
except Exception as e:
    app.logger.error(f"Failed to register font: {str(e)}")
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'Helvetica'))  # Fallback to Helvetica

@app.route('/')
@login_required
def index():
    search_query = request.args.get('search', '')
    category_id = request.args.get('category_id', type=int)
    show_completed = request.args.get('show_completed', type=int, default=0)
    show_incomplete = request.args.get('show_incomplete', type=int, default=0)
    notes_query = Note.query.filter_by(user_id=current_user.id)
    if search_query:
        notes_query = notes_query.filter(Note.title.contains(search_query) | Note.content.contains(search_query))
    if category_id:
        notes_query = notes_query.filter_by(category_id=category_id)
    if show_completed and not show_incomplete:
        notes_query = notes_query.filter_by(is_completed=True)
    elif show_incomplete and not show_completed:
        notes_query = notes_query.filter_by(is_completed=False)
    # Sort by due_date ascending, nulls last
    notes_query = notes_query.order_by(Note.due_date.asc().nulls_last())
    notes = notes_query.all()
    # Convert notes to JSON-serializable format
    notes_data = [
        {
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'category_id': note.category_id,
            'category_name': note.category.name if note.category else None,
            'category_color': note.category.color if note.category else None,
            'due_date': note.due_date.isoformat() if note.due_date else None,
            'share_id': note.share_id,
            'is_completed': note.is_completed,
            'images': json.loads(note.images) if note.images else []
        } for note in notes
    ]
    # Fetch categories and convert to JSON-serializable format
    categories = Category.query.filter_by(user_id=current_user.id).all()
    categories_data = [
        {'id': category.id, 'name': category.name, 'color': category.color or '#ffffff'}
        for category in categories
    ]
    now = datetime.now()
    return render_template(
        'index.html',
        notes=notes,
        notes_data=notes_data,
        search_query=search_query,
        categories=categories_data,  # Use serialized data
        selected_category=category_id,
        show_completed=show_completed,
        show_incomplete=show_incomplete,
        now=now
    )

def normalize_filename(filename):
    if not filename or not isinstance(filename, str):
        return 'image.jpg'
    # Chuẩn hóa Unicode về dạng NFKC để xử lý ký tự tiếng Nhật
    normalized = unicodedata.normalize('NFKC', filename)
    # Thay thế ký tự không an toàn
    safe_name = ''.join(c if c.isalnum() or c in '._-\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF' else '_' for c in normalized)
    # Loại bỏ nhiều dấu chấm và dấu chấm cuối
    safe_name = safe_name.replace('..', '.').rstrip('.')
    return safe_name or 'image.jpg'

@app.route('/add_note', methods=['GET', 'POST'])
@login_required
def add_note():
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            content = request.form.get('content')
            category_id = request.form.get('category_id')
            due_date = request.form.get('due_date')
            share = request.form.get('share') == '1'
            is_completed = request.form.get('is_completed') == '1'

            # Validate required fields
            if not title:
                flash('Title is required.', 'danger')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'error', 'message': 'Title is required'}), 400
                return redirect(url_for('index'))

            if not content:
                flash('Content is required.', 'danger')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'error', 'message': 'Content is required'}), 400
                return redirect(url_for('index'))

            # Validate category
            categories = Category.query.filter_by(user_id=current_user.id).all()
            if not categories:
                flash('No categories available. Please create a category first.', 'danger')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'error', 'message': 'No categories available'}), 400
                return redirect(url_for('index'))
            if not category_id or not Category.query.filter_by(id=category_id, user_id=current_user.id).first():
                flash('Please select a valid category.', 'danger')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'error', 'message': 'Invalid category'}), 400
                return redirect(url_for('index'))

            # Parse due_date
            due_date_utc = None
            if due_date:
                try:
                    due_date_obj = datetime.strptime(due_date, '%Y-%m-%dT%H:%M')
                    due_date_utc = due_date_obj - timedelta(hours=9)  # Convert JST to UTC
                except ValueError as e:
                    flash('Invalid due date format.', 'danger')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'status': 'error', 'message': 'Invalid due date format'}), 400
                    return redirect(url_for('index'))

            # Lưu memo trước
            note = Note(
                title=title,
                content=content,
                category_id=category_id,
                user_id=current_user.id,
                due_date=due_date_utc,
                share_id=str(uuid4()) if share else None,
                is_completed=is_completed,
                images=None
            )
            db.session.add(note)
            db.session.commit()

            # Hàm xử lý ảnh bất đồng bộ
            def process_images(note_id, files):
                with app.app_context():
                    app.logger.debug(f"Processing images for note_id {note_id}, files: {[f.filename for f in files]}")
                    images = []
                    for file in files:
                        if file and file.filename:
                            allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.heic'}
                            normalized_filename = normalize_filename(file.filename)
                            ext = os.path.splitext(normalized_filename.lower())[1]
                            if ext in allowed_extensions:
                                try:
                                    if ext == '.heic':
                                        with Image(file=file) as img:
                                            img.format = 'jpeg'
                                            img.compression_quality = 20
                                            output = io.BytesIO()
                                            img.save(file=output)
                                            image_data = output.getvalue()
                                        filename = normalized_filename.replace('.heic', '.jpg')
                                    else:
                                        image_data = file.read()
                                        filename = normalized_filename
                                    image_base64 = b64encode(image_data).decode('utf-8')
                                    images.append({
                                        'filename': filename,
                                        'data': image_base64
                                    })
                                except Exception as e:
                                    app.logger.error(f"Error processing image {normalized_filename}: {str(e)}")
                            else:
                                app.logger.warning(f"Invalid file type: {normalized_filename}")
                    if images:
                        try:
                            note = Note.query.get(note_id)
                            note.images = json.dumps(images)
                            db.session.commit()
                            app.logger.debug(f"Images saved for note_id {note_id}: {len(images)} images")
                        except Exception as e:
                            app.logger.error(f"Error saving images to DB for note_id {note_id}: {str(e)}")

            # Lấy danh sách file và xử lý bất đồng bộ
            files = request.files.getlist('images')
            app.logger.debug(f"Received files: {[f.filename for f in files if f.filename]}")
            if files and any(file.filename for file in files):
                threading.Thread(target=process_images, args=(note.id, files)).start()
            else:
                app.logger.debug("No valid image files received")

            flash('Note added successfully!', 'success')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'success',
                    'note': {
                        'id': note.id,
                        'title': note.title,
                        'content': note.content,
                        'category_id': note.category_id,
                        'category_name': note.category.name,
                        'due_date': note.due_date.strftime('%Y-%m-%dT%H:%M') if note.due_date else '',
                        'share_id': note.share_id,
                        'is_completed': bool(note.is_completed),
                        'images': []  # Trả về mảng rỗng vì ảnh đang được xử lý
                    },
                    'categories': [{'id': c.id, 'name': c.name} for c in Category.query.filter_by(user_id=current_user.id).all()]
                })
            return redirect(url_for('index'))

        except Exception as e:
            app.logger.error(f"Error in add_note: {str(e)}")
            flash('An error occurred while adding the note.', 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500
            return redirect(url_for('index'))

    categories = Category.query.filter_by(user_id=current_user.id).all()
    return redirect(url_for('index'))

@app.route('/edit_note/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_note(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'Unauthorized access.'}), 403
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            title = request.form.get('title')
            content = request.form.get('content')
            category_id = request.form.get('category_id')
            due_date = request.form.get('due_date')
            share = request.form.get('share') == '1'
            is_completed = request.form.get('is_completed') == '1'

            # Validate required fields
            if not title:
                flash('Title is required.', 'danger')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'error', 'message': 'Title is required'}), 400
                return redirect(url_for('index'))

            if not content:
                flash('Content is required.', 'danger')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'error', 'message': 'Content is required'}), 400
                return redirect(url_for('index'))

            # Validate category
            categories = Category.query.filter_by(user_id=current_user.id).all()
            if not categories:
                flash('No categories available. Please create a category first.', 'danger')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'error', 'message': 'No categories available'}), 400
                return redirect(url_for('index'))
            if not category_id or not Category.query.filter_by(id=category_id, user_id=current_user.id).first():
                flash('Please select a valid category.', 'danger')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'error', 'message': 'Invalid category'}), 400
                return redirect(url_for('index'))

            # Parse due_date
            due_date_utc = None
            if due_date:
                try:
                    due_date_obj = datetime.strptime(due_date, '%Y-%m-%dT%H:%M')
                    due_date_utc = due_date_obj - timedelta(hours=9)  # Convert JST to UTC
                except ValueError as e:
                    flash('Invalid due date format.', 'danger')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'status': 'error', 'message': 'Invalid due date format'}), 400
                    return redirect(url_for('index'))

            # Cập nhật thông tin memo
            note.title = title
            note.content = content
            note.category_id = category_id
            note.due_date = due_date_utc
            note.share_id = str(uuid4()) if share and not note.share_id else note.share_id if share else None
            note.is_completed = is_completed

            # Xử lý ảnh hiện có
            images = json.loads(note.images) if note.images else []
            keep_images = request.form.getlist('keep_images')
            app.logger.debug(f"Keep images indices: {keep_images}")
            if keep_images:
                keep_indices = [int(i) for i in keep_images if i.isdigit() and int(i) < len(images)]
                images = [images[i] for i in keep_indices]
            else:
                images = images if images else []  # Giữ nguyên nếu không có keep_images

            # Lưu memo trước khi xử lý ảnh mới
            note.images = json.dumps(images) if images else None
            db.session.commit()

            # Hàm xử lý ảnh mới bất đồng bộ
            def process_new_images(note_id, files, existing_images):
                with app.app_context():
                    app.logger.debug(f"Processing new images for note_id {note_id}, files: {[f.filename for f in files]}")
                    new_images = existing_images[:] if existing_images else []
                    for file in files:
                        if file and file.filename:
                            allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.heic'}
                            normalized_filename = normalize_filename(file.filename)
                            ext = os.path.splitext(normalized_filename.lower())[1]
                            if ext in allowed_extensions:
                                try:
                                    if ext == '.heic':
                                        with Image(file=file) as img:
                                            img.format = 'jpeg'
                                            img.compression_quality = 20
                                            output = io.BytesIO()
                                            img.save(file=output)
                                            image_data = output.getvalue()
                                        filename = normalized_filename.replace('.heic', '.jpg')
                                    else:
                                        image_data = file.read()
                                        filename = normalized_filename
                                    image_base64 = b64encode(image_data).decode('utf-8')
                                    new_images.append({
                                        'filename': filename,
                                        'data': image_base64
                                    })
                                except Exception as e:
                                    app.logger.error(f"Error processing image {normalized_filename}: {str(e)}")
                            else:
                                app.logger.warning(f"Invalid file type: {normalized_filename}")
                    try:
                        note = Note.query.get(note_id)
                        note.images = json.dumps(new_images) if new_images else None
                        db.session.commit()
                        app.logger.debug(f"Images saved for note_id {note_id}: {len(new_images)} images")
                    except Exception as e:
                        app.logger.error(f"Error saving images to DB for note_id {note_id}: {str(e)}")

            # Lấy danh sách file mới và xử lý bất đồng bộ
            files = request.files.getlist('images')
            app.logger.debug(f"Received files for edit: {[f.filename for f in files if f.filename]}")
            if files and any(file.filename for file in files):
                threading.Thread(target=process_new_images, args=(note.id, files, images)).start()
            else:
                app.logger.debug("No valid new image files received")

            flash('Note updated successfully!', 'success')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'success',
                    'note': {
                        'id': note.id,
                        'title': note.title,
                        'content': note.content,
                        'category_id': note.category_id,
                        'category_name': note.category.name,
                        'due_date': note.due_date.strftime('%Y-%m-%dT%H:%M') if note.due_date else '',
                        'share_id': note.share_id,
                        'is_completed': bool(note.is_completed),
                        'images': images
                    }
                })
            return redirect(url_for('index'))

        except Exception as e:
            app.logger.error(f"Error in edit_note: {str(e)}")
            flash('An error occurred while updating the note.', 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500
            return redirect(url_for('index'))

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        images = json.loads(note.images) if note.images else []
        return jsonify({
            'status': 'success',
            'note': {
                'id': note.id,
                'title': note.title,
                'content': note.content,
                'category_id': note.category_id,
                'category_name': note.category.name,
                'due_date': note.due_date.strftime('%Y-%m-%dT%H:%M') if note.due_date else '',
                'share_id': note.share_id,
                'is_completed': bool(note.is_completed),
                'images': images
            },
            'categories': [{'id': c.id, 'name': c.name} for c in Category.query.filter_by(user_id=current_user.id).all()]
        })

    categories = Category.query.filter_by(user_id=current_user.id).all()
    return redirect(url_for('index'))

@app.route('/get_image/<int:note_id>/<string:filename>')
@login_required
def get_image(note_id, filename):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Unauthorized access.'}), 403
    images = json.loads(note.images) if note.images else []
    image = next((img for img in images if img['filename'] == filename), None)
    if not image:
        return jsonify({'status': 'error', 'message': 'Image not found.'}), 404
    image_data = base64.b64decode(image['data'])
    return send_file(BytesIO(image_data), mimetype=f'image/{filename.split(".")[-1].lower()}')

@app.route('/toggle_complete/<int:id>', methods=['POST'])
@login_required
def toggle_complete(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    note.is_completed = not note.is_completed
    db.session.commit()
    return jsonify({'is_completed': note.is_completed})

@app.route('/delete/<int:id>')
@login_required
def delete_note(id):
    note = Note.query.get_or_404(id)
    if note.user_id == current_user.id:
        db.session.delete(note)
        db.session.commit()
        flash('Note deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/export/<int:id>')
@login_required
def export_note(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('index'))
    file_content = f"Title: {note.title}\n\n{note.content}\n\nCategory: {note.category.name if note.category else 'None'}"
    file = BytesIO(file_content.encode('utf-8'))
    return send_file(file, download_name=f"{note.title}.txt", as_attachment=True)

@app.route('/export_pdf/<int:id>')
@login_required
def export_pdf(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('index'))
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    try:
        p.setFont('DejaVuSans', 12)
    except:
        p.setFont('Helvetica', 12)  # Fallback font
    p.drawString(100, 750, note.title)
    y = 700
    for line in note.content.split('\n'):
        p.drawString(100, y, line)
        y -= 20
    p.drawString(100, y, f"Category: {note.category.name if note.category else 'None'}")
    y -= 30

    # Thêm ảnh vào PDF
    images = json.loads(note.images) if note.images else []
    for img in images:
        try:
            img_data = base64.b64decode(img['data'])
            img_buffer = BytesIO(img_data)
            # Chèn ảnh, resize cho phù hợp trang
            from reportlab.lib.utils import ImageReader
            image = ImageReader(img_buffer)
            iw, ih = image.getSize()
            max_width = 400
            max_height = 300
            scale = min(max_width / iw, max_height / ih, 1)
            draw_width = iw * scale
            draw_height = ih * scale
            if y - draw_height < 50:
                p.showPage()
                y = 750
            p.drawImage(image, 100, y - draw_height, width=draw_width, height=draw_height)
            y -= draw_height + 20
        except Exception as e:
            # Nếu lỗi ảnh, bỏ qua ảnh đó
            continue

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, download_name=f"{note.title}.pdf", as_attachment=True)

@app.route('/share/<share_id>')
def share_note(share_id):
    note = Note.query.filter_by(share_id=share_id).first_or_404()
    return render_template('share_note.html', note=note)

@app.route('/import', methods=['GET', 'POST'])
@login_required
def import_note():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.txt'):
            try:
                content = file.read().decode('utf-8')
                lines = content.split('\n', 2)
                title = lines[0].replace('Title: ', '') if lines[0].startswith('Title: ') else 'Imported Note'
                note_content = lines[2].split('Category: ')[0] if len(lines) > 2 else content
                category_name = lines[2].split('Category: ')[1].strip() if len(lines) > 2 and 'Category: ' in lines[2] else None
                category = Category.query.filter_by(name=category_name, user_id=current_user.id).first()
                category_id = category.id if category else None
                note = Note(title=title, content=note_content, user_id=current_user.id, category_id=category_id)
                db.session.add(note)
                db.session.commit()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'status': 'success',
                        'message': 'Note imported successfully!',
                        'note': {
                            'id': note.id,
                            'title': note.title,
                            'content': note.content,
                            'category_id': note.category_id,
                            'category_name': category_name,
                            'is_completed': note.is_completed
                        }
                    })
                flash('Note imported successfully!', 'success')
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'error', 'message': f'Failed to import note: {str(e)}'}), 400
                flash(f'Failed to import note: {str(e)}', 'danger')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': 'Please upload a .txt file!'}), 400
            flash('Please upload a .txt file!', 'danger')
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return redirect(url_for('index'))
    return render_template('import_note.html')

@app.route('/calendar')
@login_required
def calendar():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    # Serialize categories for JavaScript
    categories_data = [{'id': c.id, 'name': c.name, 'color': c.color or '#ffffff'} for c in categories]
    return render_template('calendar.html', categories=categories, categories_data=categories_data)

@app.route('/notes')
@login_required
def get_notes():
    notes = Note.query.filter_by(user_id=current_user.id).all()
    events = [
        {
            'id': note.id,
            'title': note.title,
            'start': note.due_date.isoformat() if note.due_date else None,
            'backgroundColor': note.category.color if note.category and note.category.color else '#ffffff',
            'is_completed': note.is_completed
        }
        for note in notes if note.due_date
    ]
    return jsonify(events)

@app.route('/manage_categories')
@login_required
def manage_categories():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'status': 'success',
            'categories': [{'id': c.id, 'name': c.name, 'color': c.color or '#ffffff'} for c in categories]
        })
    return render_template('manage_categories.html', categories=categories)

@app.route('/add_category', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        name = request.form['name']
        color = request.form['color']
        if Category.query.filter_by(name=name, user_id=current_user.id).first():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': 'Category already exists!'}), 400
            flash('Category already exists!', 'danger')
        else:
            category = Category(name=name, user_id=current_user.id, color=color)
            db.session.add(category)
            db.session.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'success',
                    'category': {'id': category.id, 'name': category.name, 'color': category.color or '#ffffff'}
                })
            flash('Category added successfully!', 'success')
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return redirect(url_for('manage_categories'))
    return render_template('add_category.html')

@app.route('/edit_category/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    category = Category.query.get_or_404(id)
    if category.user_id != current_user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'Unauthorized access!'}), 403
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('manage_categories'))
    if request.method == 'POST':
        name = request.form['name']
        color = request.form['color']
        if Category.query.filter_by(name=name, user_id=current_user.id).first() and name != category.name:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': 'Category name already exists!'}), 400
            flash('Category name already exists!', 'danger')
        else:
            category.name = name
            category.color = color
            db.session.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'status': 'success',
                    'category': {'id': category.id, 'name': category.name, 'color': category.color or '#ffffff'}
                })
            flash('Category updated successfully!', 'success')
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return redirect(url_for('manage_categories'))
    return render_template('edit_category.html', category=category)

@app.route('/delete_category/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    if category.user_id == current_user.id:
        Note.query.filter_by(category_id=id).update({'category_id': None})
        db.session.delete(category)
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'success'})
        flash('Category deleted successfully!', 'success')
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': 'Unauthorized access!'}), 403
        flash('Unauthorized access!', 'danger')
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return redirect(url_for('manage_categories'))
    return jsonify({'status': 'success'})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if verify_password(password):
            user = User()
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid password', 'danger')
    return render_template('login.html')

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    new_password = request.form['new_password']
    if new_password:
        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        with open('user.txt', 'w') as f:
            f.write(hashed.decode('utf-8'))
        flash('Password changed successfully!', 'success')
    else:
        flash('Please enter a new password', 'danger')
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/sync', methods=['POST'])
@login_required
def sync_notes():
    try:
        data = request.get_json()
        app.logger.debug(f"Received sync data: {data}")
        for note in data.get('notes', []):
            existing_note = Note.query.get(note.get('id'))
            if existing_note and existing_note.user_id == current_user.id:
                existing_note.title = note['title']
                existing_note.content = note['content']
                existing_note.category_id = note.get('category_id')
                due_date = note.get('due_date')
                existing_note.due_date = datetime.fromisoformat(due_date) if due_date else None
                existing_note.is_completed = note.get('is_completed', False)
            else:
                category = Category.query.filter_by(id=note.get('category_id'), user_id=current_user.id).first()
                new_note = Note(
                    title=note['title'],
                    content=note['content'],
                    user_id=current_user.id,
                    category_id=category.id if category else None,
                    due_date=datetime.fromisoformat(due_date) if (due_date := note.get('due_date')) else None,
                    is_completed=note.get('is_completed', False)
                )
                db.session.add(new_note)
        db.session.commit()
        notes = Note.query.filter_by(user_id=current_user.id).all()
        response = {
            'notes': [
                {
                    'id': note.id,
                    'title': note.title,
                    'content': note.content,
                    'category_id': note.category_id if note.category_id else None,
                    'due_date': note.due_date.isoformat() if note.due_date else None,
                    'is_completed': note.is_completed
                } for note in notes
            ]
        }
        app.logger.debug(f"Sync response: {response}")
        return response
    except Exception as e:
        app.logger.error(f"Sync error: {str(e)}")
        return {'error': str(e)}, 500

import os

@app.route('/db_size')
@login_required
def db_size():
    db_path = os.path.join(app.instance_path, 'memo.db')  # Sửa lại đường dẫn này
    try:
        size_bytes = os.path.getsize(db_path)
        size_kb = round(size_bytes / 1024, 2)
        size_mb = round(size_kb / 1024, 2)
        return jsonify({'size_bytes': size_bytes, 'size_kb': size_kb, 'size_mb': size_mb})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/links')
@login_required
def get_links():
    links = []
    try:
        with open('link.txt', 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    links.append(url)
    except Exception as e:
        app.logger.error(f"Error reading link.txt: {e}")
    return jsonify({'links': links})

@app.route('/links', methods=['GET', 'POST'])
@login_required
def links():
    if request.method == 'POST':
        data = request.get_json()
        links = data.get('links', [])
        try:
            with open('link.txt', 'w', encoding='utf-8') as f:
                for link in links:
                    f.write(link.strip() + '\n')
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    # GET như cũ
    links = []
    try:
        with open('link.txt', 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    links.append(url)
    except Exception as e:
        app.logger.error(f"Error reading link.txt: {e}")
    return jsonify({'links': links})


# Diary app routes

@diary_app.context_processor
def inject_theme_quote():
    theme = session.get('theme', 'light')
    return dict(theme=theme)


@app.route('/Diary/new', methods=['GET', 'POST'])
def new_diary():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        color = request.form['color']
        with diary_app.app_context():
            diary = Diary(title=title, content=content, color=color)
            db_diary.session.add(diary)
            db_diary.session.commit()
        flash('Diary entry saved!', 'success')
        return redirect(url_for('diary_list'))
    return render_template('Diary/new_diary.html')

@app.route('/Diary/edit/<int:id>', methods=['GET', 'POST'])
def edit_diary(id):
    with diary_app.app_context():
        diary = Diary.query.get_or_404(id)
        if request.method == 'POST':
            diary.title = request.form['title']
            diary.content = request.form['content']
            diary.color = request.form['color']
            db_diary.session.commit()
            flash('Diary entry updated!', 'success')
            return redirect(url_for('diary_grid'))
    return render_template('Diary/edit_diary.html', diary=diary)

@app.route('/Diary/grid')
def diary_grid():
    with diary_app.app_context():
        diaries = Diary.query.all()
    return render_template('Diary/diary_grid.html', diaries=diaries)

@app.route('/Diary/list')
def diary_list():
    with diary_app.app_context():
        diaries = Diary.query.order_by(Diary.date.desc()).all()
    return render_template('Diary/diary_list.html', diaries=diaries)

@app.route('/change_slogan', methods=['POST'])
def change_slogan():
    new_slogan_text = request.form['new_slogan']
    if not new_slogan_text or len(new_slogan_text) > 200:
        flash('Slogan must be between 1 and 200 characters.', 'danger')
        return redirect(request.referrer or url_for('Diary/diary_grid'))
    with diary_app.app_context():
        slogan = Slogan.query.first()
        if slogan:
            slogan.text = new_slogan_text
        else:
            slogan = Slogan(text=new_slogan_text)
            db_diary.session.add(slogan)
        db_diary.session.commit()
    flash('Slogan updated successfully!', 'success')
    return redirect(request.referrer or url_for('Diary/diary_grid'))

@app.context_processor
def inject_theme():
    # Theme lấy từ session hoặc mặc định
    theme = session.get('theme', 'light')
    print(theme)
    username, birthday = get_user_info()
    days_alive = 0
    if birthday:
        try:
            dob = datetime.strptime(birthday, '%Y-%m-%d').date()
            days_alive = (date.today() - dob).days
        except Exception:
            pass
    # Lấy slogan từ DB diary
    with diary_app.app_context():
        slogan = Slogan.query.first()
        slogan_text = slogan.text if slogan else "Write your story, live your journey."
    return dict(
        theme=theme,
        username=username,
        days_alive=days_alive,
        slogan=slogan_text
    )

# Custom Jinja2 filter to format numbers with thousands separators
@app.template_filter('format_thousands')
def format_thousands(number):
    try:
        return "{:,}".format(int(number))
    except (ValueError, TypeError):
        return number

# Quote app routes
@quote_app.context_processor
def inject_theme_quote():
    theme = session.get('theme', 'light')
    return dict(theme=theme)

@app.route('/quotes', methods=['GET', 'POST'])
def quotes():
    with quote_app.app_context():
        categories = QuoteCategory.query.order_by(QuoteCategory.name).all()
        quote = None
        selected_category = None

        all_quotes = Quote.query.all()

        if request.method == 'POST':
            if 'category' in request.form and request.form['category']:
                selected_category = request.form['category']
                category = QuoteCategory.query.filter_by(name=selected_category).first()
                quotes_list = Quote.query.filter_by(category=category).all() if category else []
                if quotes_list:
                    quote = random.choice(quotes_list)
            else:
                if all_quotes:
                    quote = random.choice(all_quotes)

        if not quote and all_quotes:
            quote = random.choice(all_quotes)

        return render_template('Quote/quotes.html', quote=quote, categories=categories,
                               selected_category=selected_category)
        

@app.route('/quotes/manage', methods=['GET', 'POST'])
def manage_quotes():
    with quote_app.app_context():
        if request.method == 'POST':
            content = request.form.get('content', '').strip()
            category_name = request.form.get('category', '').strip()
            # Kiểm tra trùng lặp
            existing_quotes = [q.content for q in Quote.query.all()]
            for existing_content in existing_quotes:
                similarity = difflib.SequenceMatcher(None, content.lower(), existing_content.lower()).ratio()
                if similarity >= 0.8:
                    flash("Trích dẫn này quá giống (≥80%) với một trích dẫn đã tồn tại! Vui lòng nhập trích dẫn khác.", "error")
                    break
            else:
                if content and category_name:
                    category = QuoteCategory.query.filter_by(name=category_name).first()
                    if not category:
                        category = QuoteCategory(name=category_name)
                        db_quote.session.add(category)
                        db_quote.session.commit()
                    db_quote.session.add(Quote(content=content, category=category))
                    db_quote.session.commit()
                    flash("Trích dẫn đã được thêm thành công!", "success")
        quotes = Quote.query.order_by(Quote.content).all()
        categories = QuoteCategory.query.order_by(QuoteCategory.name).all()
        category_counts = db_quote.session.query(QuoteCategory, db_quote.func.count(Quote.id)).outerjoin(Quote).group_by(QuoteCategory.id).all()
        return render_template('Quote/manage_quotes.html', quotes=quotes, categories=categories, category_counts=category_counts)

@app.route('/quotes/edit/<int:id>', methods=['POST'])
def edit_quote(id):
    with quote_app.app_context():
        content = request.form['content']
        category_name = request.form['category']
        quote = Quote.query.get_or_404(id)
        category = QuoteCategory.query.filter_by(name=category_name).first()
        if not category:
            category = QuoteCategory(name=category_name)
            db_quote.session.add(category)
            db_quote.session.commit()
        quote.content = content
        quote.category = category
        db_quote.session.commit()
        flash("Trích dẫn đã được sửa thành công!", "success")
        return redirect(url_for('manage_quotes'))


@app.route('/quotes/delete/<int:id>')
def delete_quote(id):
    with quote_app.app_context():
        quote = Quote.query.get_or_404(id)
        db_quote.session.delete(quote)
        db_quote.session.commit()
        flash("Trích dẫn đã được xóa thành công!", "success")
        return redirect(url_for('manage_quotes'))

@app.route('/quotes/delete_category/<int:category_id>')
def delete_quote_category(category_id):
    with quote_app.app_context():
        category = QuoteCategory.query.get_or_404(category_id)
        quote_count = Quote.query.filter_by(category=category).count()
        if quote_count > 0:
            flash(
                f"Không thể xóa nguồn '{category.name}' vì đang chứa {quote_count} trích dẫn. Vui lòng xóa hết trích dẫn trong nguồn này trước.",
                "error")
        else:
            db_quote.session.delete(category)
            db_quote.session.commit()
            flash(f"Nguồn '{category.name}' đã được xóa thành công.", "success")
        return redirect(url_for('manage_quotes'))

if __name__ == '__main__':
    app.run(debug=True)