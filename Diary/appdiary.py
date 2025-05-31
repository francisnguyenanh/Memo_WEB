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

def get_user_info():
    try:
        with open('Diary/userinfor.txt', 'r', encoding='utf-8') as f:
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
    


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('diary_grid'))
    return redirect(url_for('login'))


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


@app.route('/diary/new', methods=['GET', 'POST'])
def new_diary():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        color = request.form['color']
        diary = Diary(title=title, content=content, color=color)
        db.session.add(diary)
        db.session.commit()
        flash('Diary entry saved!', 'success')
        return redirect(url_for('diary_list'))
    return render_template('new_diary.html')

@app.route('/diary/edit/<int:id>', methods=['GET', 'POST'])
def edit_diary(id):
    diary = Diary.query.get_or_404(id)
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
    diaries = Diary.query.all()
    return render_template('diary_grid.html', diaries=diaries)

@app.route('/diary/list')
def diary_list():
    diaries = Diary.query.order_by(Diary.date.desc()).all()
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
    username, birthday = get_user_info()
    days_alive = 0
    if birthday:
        try:
            dob = datetime.strptime(birthday, '%Y-%m-%d').date()
            days_alive = (date.today() - dob).days
        except Exception:
            pass
    slogan = Slogan.query.first()
    return dict(
        username=username,
        days_alive=days_alive,
        slogan=slogan.text if slogan else "Write your story, live your journey."
    )
    
if __name__ == '__main__':
    app.run(debug=True)