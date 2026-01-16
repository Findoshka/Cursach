"""
Миграция: создание таблиц support_tickets и support_messages.
"""

from app import app
from models import db

with app.app_context():
    try:
        # Создание таблицы support_tickets
        db.engine.execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject VARCHAR(500) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'новая',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        print("Таблица support_tickets успешно создана.")
    except Exception as e:
        print(f"Ошибка создания таблицы support_tickets: {e}")
    
    try:
        # Создание таблицы support_messages
        db.engine.execute('''
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                is_support BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        print("Таблица support_messages успешно создана.")
    except Exception as e:
        print(f"Ошибка создания таблицы support_messages: {e}")
