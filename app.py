from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Response, jsonify
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
from datetime import datetime
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///memo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
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
class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(80), nullable=False)
    tags = db.Column(db.String(200), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    share_id = db.Column(db.String(36), nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    category = db.relationship('Category', backref='notes')

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

# Register font for Vietnamese support
pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))

@app.route('/')
@login_required
def index():
    search_query = request.args.get('search', '')
    category_id = request.args.get('category_id', type=int)
    show_completed = request.args.get('show_completed', type=int, default=0)
    notes_query = Note.query.filter_by(user_id=current_user.id)
    if search_query:
        notes_query = notes_query.filter(Note.title.contains(search_query) | Note.content.contains(search_query))
    if category_id:
        notes_query = notes_query.filter_by(category_id=category_id)
    if show_completed:
        notes_query = notes_query.filter_by(is_completed=True)
    # Sort by due_date ascending, nulls last
    notes_query = notes_query.order_by(Note.due_date.asc().nulls_last())
    notes = notes_query.all()
    # Convert notes to JSON-serializable format
    notes_data = [
        {
            'id': note.id,
            'title': note.title,
            'content': note.content,
            'tags': note.tags,
            'category_id': note.category_id,
            'category_name': note.category.name if note.category else None,
            'category_color': note.category.color if note.category else None,
            'due_date': note.due_date.isoformat() if note.due_date else None,
            'share_id': note.share_id,
            'is_completed': note.is_completed
        } for note in notes
    ]
    categories = Category.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', notes=notes, notes_data=notes_data, search_query=search_query,
                         categories=categories, selected_category=category_id, show_completed=show_completed)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_note():
    categories = Category.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        tags = request.form.get('tags')
        category_id = request.form.get('category_id', type=int)
        due_date = request.form.get('due_date')
        due_date = datetime.strptime(due_date, '%Y-%m-%dT%H:%M') if due_date else None
        share_id = str(uuid.uuid4()) if request.form.get('share') else None
        is_completed = bool(request.form.get('is_completed'))
        note = Note(title=title, content=content, tags=tags, user_id=current_user.id,
                    category_id=category_id, due_date=due_date, share_id=share_id, is_completed=is_completed)
        db.session.add(note)
        db.session.commit()
        flash('Note added successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('add_note.html', categories=categories)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_note(id):
    note = Note.query.get_or_404(id)
    if note.user_id != current_user.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('index'))
    categories = Category.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        note.title = request.form['title']
        note.content = request.form['content']
        note.tags = request.form.get('tags')
        note.category_id = request.form.get('category_id', type=int)
        due_date = request.form.get('due_date')
        note.due_date = datetime.strptime(due_date, '%Y-%m-%dT%H:%M') if due_date else None
        note.share_id = str(uuid.uuid4()) if request.form.get('share') else note.share_id
        note.is_completed = bool(request.form.get('is_completed'))
        db.session.commit()
        flash('Note updated successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('edit_note.html', note=note, categories=categories)

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
    file_content = f"Title: {note.title}\n\n{note.content}\n\nTags: {note.tags or 'None'}\nCategory: {note.category.name if note.category else 'None'}"
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
    p.setFont('DejaVuSans', 12)
    p.drawString(100, 750, note.title)
    y = 700
    for line in note.content.split('\n'):
        p.drawString(100, y, line)
        y -= 20
    p.drawString(100, y, f"Tags: {note.tags or 'None'}")
    p.drawString(100, y - 20, f"Category: {note.category.name if note.category else 'None'}")
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
            content = file.read().decode('utf-8')
            lines = content.split('\n', 2)
            title = lines[0].replace('Title: ', '') if lines[0].startswith('Title: ') else 'Imported Note'
            note_content = lines[2].split('Tags: ')[0] if len(lines) > 2 else content
            tags = lines[2].split('Tags: ')[1].split('\nCategory: ')[0] if len(lines) > 2 and 'Tags: ' in lines[2] else None
            category_name = lines[2].split('Category: ')[1] if len(lines) > 2 and 'Category: ' in lines[2] else None
            category = Category.query.filter_by(name=category_name, user_id=current_user.id).first()
            category_id = category.id if category else None
            note = Note(title=title, content=note_content, tags=tags, user_id=current_user.id, category_id=category_id)
            db.session.add(note)
            db.session.commit()
            flash('Note imported successfully!', 'success')
        else:
            flash('Please upload a .txt file!', 'danger')
        return redirect(url_for('index'))
    return render_template('import_note.html')

@app.route('/add_category', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        name = request.form['name']
        color = request.form['color']
        if Category.query.filter_by(name=name, user_id=current_user.id).first():
            flash('Category already exists!', 'danger')
        else:
            category = Category(name=name, user_id=current_user.id, color=color)
            db.session.add(category)
            db.session.commit()
            flash('Category added successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('add_category.html')

@app.route('/edit_category/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_category(id):
    category = Category.query.get_or_404(id)
    if category.user_id != current_user.id:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form['name']
        color = request.form['color']
        if Category.query.filter_by(name=name, user_id=current_user.id).first() and name != category.name:
            flash('Category name already exists!', 'danger')
        else:
            category.name = name
            category.color = color
            db.session.commit()
            flash('Category updated successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('edit_category.html', category=category)

@app.route('/delete_category/<int:id>')
@login_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    if category.user_id == current_user.id:
        # Set category_id to null for all notes in this category
        Note.query.filter_by(category_id=id).update({'category_id': None})
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted successfully!', 'success')
    return redirect(url_for('index'))

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
                existing_note.tags = note.get('tags')
                existing_note.category_id = note.get('category_id')
                due_date = note.get('due_date')
                existing_note.due_date = datetime.fromisoformat(due_date) if due_date else None
                existing_note.is_completed = note.get('is_completed', False)
            else:
                category = Category.query.filter_by(id=note.get('category_id'), user_id=current_user.id).first()
                new_note = Note(
                    title=note['title'],
                    content=note['content'],
                    tags=note.get('tags'),
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
                    'tags': note.tags if note.tags else None,
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

if __name__ == '__main__':
    app.run(debug=True)