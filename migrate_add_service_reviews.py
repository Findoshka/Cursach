"""
Миграция: добавление таблицы service_reviews для отзывов на услуги.
"""

from app import app
from models import db

with app.app_context():
    try:
        db.engine.execute("""
            CREATE TABLE IF NOT EXISTS service_reviews (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_service_reviews_service_user UNIQUE (service_id, user_id),
                FOREIGN KEY(service_id) REFERENCES services (id),
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
        """)
        db.engine.execute("CREATE INDEX IF NOT EXISTS ix_service_reviews_service_id ON service_reviews(service_id)")
        db.engine.execute("CREATE INDEX IF NOT EXISTS ix_service_reviews_user_id ON service_reviews(user_id)")
        db.engine.execute("CREATE INDEX IF NOT EXISTS ix_service_reviews_created_at ON service_reviews(created_at)")
        print("Таблица service_reviews успешно создана.")
    except Exception as e:
        print(f"Ошибка: {e}")
