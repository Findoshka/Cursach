"""
Скрипт для создания тестовых пользователей в базе данных.
Используйте этот скрипт, если пользователи не были созданы автоматически.
"""

from app import app
from models import db, User
from auth import hash_password

with app.app_context():
    # Создание администратора
    if User.query.filter_by(username='admin').first() is None:
        admin = User(
            username='admin',
            password_hash=hash_password('admin'),
            role='admin'
        )
        db.session.add(admin)
        print("✓ Создан администратор: логин 'admin', пароль 'admin'")
    else:
        print("✗ Администратор 'admin' уже существует")
    
    # Создание пользователя
    if User.query.filter_by(username='user').first() is None:
        user = User(
            username='user',
            password_hash=hash_password('user'),
            role='user'
        )
        db.session.add(user)
        print("✓ Создан пользователь: логин 'user', пароль 'user'")
    else:
        print("✗ Пользователь 'user' уже существует")
    
    db.session.commit()
    print("\nГотово! Теперь вы можете войти в систему.")
