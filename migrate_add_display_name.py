"""
Миграция: добавление поля display_name в таблицу users.
"""

from app import app
from models import db

with app.app_context():
    try:
        db.engine.execute('ALTER TABLE users ADD COLUMN display_name VARCHAR(80)')
        print("Поле display_name успешно добавлено.")
    except Exception as e:
        if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
            print("Поле display_name уже существует.")
        else:
            print(f"Ошибка: {e}")
