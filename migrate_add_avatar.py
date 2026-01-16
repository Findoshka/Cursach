"""
Миграция: добавление поля avatar_filename в таблицу users.
"""

from app import app
from models import db

with app.app_context():
    try:
        db.engine.execute('ALTER TABLE users ADD COLUMN avatar_filename VARCHAR(255)')
        print("Поле avatar_filename успешно добавлено.")
    except Exception as e:
        if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
            print("Поле avatar_filename уже существует.")
        else:
            print(f"Ошибка: {e}")
