"""
Миграция: добавление полей email, email_verified, email_verification_token в таблицу users.
"""

from app import app
from models import db

with app.app_context():
    try:
        db.engine.execute('ALTER TABLE users ADD COLUMN email VARCHAR(255)')
        print("Поле email успешно добавлено.")
    except Exception as e:
        if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
            print("Поле email уже существует.")
        else:
            print(f"Ошибка: {e}")
    
    try:
        db.engine.execute('ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0')
        print("Поле email_verified успешно добавлено.")
    except Exception as e:
        if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
            print("Поле email_verified уже существует.")
        else:
            print(f"Ошибка: {e}")
    
    try:
        db.engine.execute('ALTER TABLE users ADD COLUMN email_verification_token VARCHAR(255)')
        print("Поле email_verification_token успешно добавлено.")
    except Exception as e:
        if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
            print("Поле email_verification_token уже существует.")
        else:
            print(f"Ошибка: {e}")
