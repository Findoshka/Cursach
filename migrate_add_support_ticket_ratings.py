"""
Миграция: добавление таблицы support_ticket_ratings для оценок поддержки.
"""

from app import app
from models import db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS support_ticket_ratings (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_support_ticket_ratings_ticket UNIQUE (ticket_id),
                FOREIGN KEY(ticket_id) REFERENCES support_tickets (id),
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
        """))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_support_ticket_ratings_ticket_id ON support_ticket_ratings(ticket_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_support_ticket_ratings_user_id ON support_ticket_ratings(user_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_support_ticket_ratings_created_at ON support_ticket_ratings(created_at)"))
        db.session.commit()
        print("Таблица support_ticket_ratings успешно создана.")
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка: {e}")
