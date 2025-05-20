import os
import re
import random
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///instance/database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

SERVERS = [
    "RED", "GREEN", "BLUE", "YELLOW", "ORANGE", "PURPLE", "LIME", "PINK", "CHERRY", "BLACK",
    "INDIGO", "WHITE", "MAGENTA", "CRIMSON", "GOLD", "AZURE", "PLATINUM", "AQUA", "GRAY", "ICE"
]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)

class TimeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    server = db.Column(db.String(50))
    nickname = db.Column(db.String(50))
    password = db.Column(db.String(50))
    hours = db.Column(db.Integer)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, server_default=db.func.now())

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin123')),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Этот username уже занят', 'error')
            return redirect(url_for('register'))
        
        user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация успешна! Теперь войдите.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            flash('Неверный username или пароль', 'error')
            return redirect(url_for('login'))
        
        if user.is_banned:
            flash('Ваш аккаунт заблокирован', 'error')
            return redirect(url_for('login'))
        
        session['user_id'] = user.id
        flash('Вход выполнен успешно!', 'success')
        
        if user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))

@app.route('/user')
def user_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if user.is_banned:
        flash('Ваш аккаунт заблокирован', 'error')
        return redirect(url_for('logout'))
    
    requests = TimeRequest.query.filter_by(user_id=user.id).order_by(TimeRequest.created_at.desc()).all()
    return render_template('user.html', user=user, requests=requests, servers=SERVERS)

@app.route('/request_time', methods=['POST'])
def request_time():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if user.is_banned:
        flash('Ваш аккаунт заблокирован', 'error')
        return redirect(url_for('logout'))
    
    server = request.form['server']
    nickname = request.form['nickname']
    password = request.form['password']
    
    if not re.match(r'^[a-zA-Z0-9_]+$', nickname) or '_' not in nickname:
        flash('Неверный формат никнейма', 'error')
        return redirect(url_for('user_dashboard'))
    
    if len(password) < 6 or len(password) > 16:
        flash('Пароль должен быть от 6 до 16 символов', 'error')
        return redirect(url_for('user_dashboard'))
    
    time_request = TimeRequest(
        user_id=user.id,
        server=server,
        nickname=nickname,
        password=password,
        hours=random.randint(100, 550)
    )
    db.session.add(time_request)
    db.session.commit()
    
    flash('Запрос отправлен! Ваше время будет показано после проверки.', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        return redirect(url_for('user_dashboard'))
    
    pending_requests = TimeRequest.query.filter_by(status='pending').order_by(TimeRequest.created_at.desc()).all()
    users = User.query.order_by(User.username).all()
    
    return render_template('admin.html', user=user, requests=pending_requests, users=users)

@app.route('/admin/action/<int:request_id>', methods=['POST'])
def admin_action(request_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    admin = User.query.get(session['user_id'])
    if not admin.is_admin:
        return redirect(url_for('user_dashboard'))
    
    time_request = TimeRequest.query.get_or_404(request_id)
    action = request.form['action']
    
    if action == 'approve':
        time_request.status = 'approved'
        db.session.commit()
        flash('Запрос одобрен', 'success')
    elif action == 'reject':
        time_request.status = 'rejected'
        db.session.commit()
        flash('Запрос отклонен', 'warning')
    elif action == 'ban':
        user = User.query.get(time_request.user_id)
        user.is_banned = True
        db.session.commit()
        flash('Пользователь заблокирован', 'danger')
    
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))