"""
Миграция: добавление поля user_id в таблицу applications.
"""

from app import app
from models import db

with app.app_context():
    try:
        db.engine.execute('ALTER TABLE applications ADD COLUMN user_id INTEGER')
        print("Поле user_id успешно добавлено.")
    except Exception as e:
        if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
            print("Поле user_id уже существует.")
        else:
            print(f"Ошибка: {e}")
