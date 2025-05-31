from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///diary.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    theme_color = db.Column(db.String(7), default='#ffffff')
    date_of_birth = db.Column(db.Date, nullable=False)

# Diary model
class Diary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    color = db.Column(db.String(7), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Slogan model
class Slogan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)

# Create database and initialize default slogan
with app.app_context():
    db.create_all()
    if not Slogan.query.first():
        default_slogan = Slogan(text="Write your story, live your journey.")
        db.session.add(default_slogan)
        db.session.commit()

# Custom Jinja2 filter to format numbers with thousands separators
@app.template_filter('format_thousands')
def format_thousands(number):
    try:
        return "{:,}".format(int(number))
    except (ValueError, TypeError):
        return number

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('diary_grid'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('diary_grid'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        dob = request.form['date_of_birth']
        try:
            dob_date = datetime.strptime(dob, '%Y-%m-%d').date()
            if dob_date > date.today():
                flash('Date of birth cannot be in the future', 'danger')
                return render_template('register.html')
        except ValueError:
            flash('Invalid date format', 'danger')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
        else:
            user = User(username=username, password=password, date_of_birth=dob_date)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/popup_register', methods=['POST'])
def popup_register():
    username = request.form['popup_username']
    password = request.form['popup_password']
    dob = request.form['popup_date_of_birth']
    try:
        dob_date = datetime.strptime(dob, '%Y-%m-%d').date()
        if dob_date > date.today():
            flash('Date of birth cannot be in the future', 'danger')
            return redirect(request.referrer or url_for('index'))
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(request.referrer or url_for('index'))
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'danger')
    else:
        user = User(username=username, password=password, date_of_birth=dob_date)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/change_slogan', methods=['POST'])
def change_slogan():
    new_slogan_text = request.form['new_slogan']
    if not new_slogan_text or len(new_slogan_text) > 200:
        flash('Slogan must be between 1 and 200 characters.', 'danger')
        return redirect(request.referrer or url_for('index'))
    slogan = Slogan.query.first()
    if slogan:
        slogan.text = new_slogan_text
    else:
        slogan = Slogan(text=new_slogan_text)
        db.session.add(slogan)
    db.session.commit()
    flash('Slogan updated successfully!', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/delete_user', methods=['POST'])
def delete_user():
    if 'user_id' not in session:
        flash('Please login to perform this action.', 'danger')
        return redirect(url_for('login'))
    user_id = request.form.get('user_id')
    if not user_id:
        flash('No user selected.', 'danger')
        return redirect(request.referrer or url_for('index'))
    try:
        user = User.query.get_or_404(int(user_id))
        # Delete all diaries of the user
        Diary.query.filter_by(user_id=user.id).delete()
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        # If the current user deletes themselves, log them out
        if user.id == session['user_id']:
            session.pop('user_id', None)
            flash(f'User {user.username} and all their data deleted successfully. You have been logged out.', 'success')
            return redirect(url_for('login'))
        flash(f'User {user.username} and all their data deleted successfully.', 'success')
    except ValueError:
        flash('Invalid user ID.', 'danger')
    return redirect(request.referrer or url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/diary/new', methods=['GET', 'POST'])
def new_diary():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        color = request.form['color']
        diary = Diary(title=title, content=content, color=color, user_id=session['user_id'])
        db.session.add(diary)
        db.session.commit()
        flash('Diary entry saved!', 'success')
        return redirect(url_for('diary_list'))
    return render_template('new_diary.html')

@app.route('/diary/edit/<int:id>', methods=['GET', 'POST'])
def edit_diary(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    diary = Diary.query.get_or_404(id)
    if diary.user_id != session['user_id']:
        flash('Unauthorized', 'danger')
        return redirect(url_for('diary_grid'))
    if request.method == 'POST':
        diary.title = request.form['title']
        diary.content = request.form['content']
        diary.color = request.form['color']
        db.session.commit()
        flash('Diary entry updated!', 'success')
        return redirect(url_for('diary_grid'))
    return render_template('edit_diary.html', diary=diary)

@app.route('/diary/grid')
def diary_grid():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    diaries = Diary.query.filter_by(user_id=session['user_id']).all()
    return render_template('diary_grid.html', diaries=diaries)

@app.route('/diary/list')
def diary_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    diaries = Diary.query.filter_by(user_id=session['user_id']).order_by(Diary.date.desc()).all()
    return render_template('diary_list.html', diaries=diaries)

@app.route('/set_theme', methods=['POST'])
def set_theme():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    color = request.form['theme_color']
    user = User.query.get(session['user_id'])
    if user:
        user.theme_color = color
        db.session.commit()
    return redirect(request.referrer or url_for('diary_grid'))

@app.context_processor
def inject_theme():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            days_alive = (date.today() - user.date_of_birth).days
            slogan = Slogan.query.first()
            users = User.query.all()  # For delete user dropdown
            return dict(theme_color=user.theme_color, days_alive=days_alive, slogan=slogan.text if slogan else "Write your story, live your journey.", users=users)
    users = User.query.all()  # For delete user dropdown when not logged in
    return dict(theme_color='#ffffff', days_alive=0, slogan=Slogan.query.first().text if Slogan.query.first() else "Write your story, live your journey.", users=users)

if __name__ == '__main__':
    app.run(debug=True)