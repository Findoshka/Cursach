"""
Миграция: создание таблицы chat_messages для истории чата с ИИ-ассистентом.
"""

from app import app
from models import db

with app.app_context():
    try:
        db.engine.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                is_bot BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        print("Таблица chat_messages успешно создана.")
    except Exception as e:
        print(f"Ошибка создания таблицы chat_messages: {e}")
