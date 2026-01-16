"""
Миграция: добавление поля image_filename в таблицу support_messages.
"""

from app import app
from models import db

with app.app_context():
    try:
        db.engine.execute('ALTER TABLE support_messages ADD COLUMN image_filename VARCHAR(255)')
        print("Поле image_filename успешно добавлено в support_messages.")
    except Exception as e:
        if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
            print("Поле image_filename уже существует.")
        else:
            print(f"Ошибка: {e}")
