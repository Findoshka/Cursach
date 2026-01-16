"""
Миграция: добавление таблицы admin_activities для логов действий администраторов.
"""

from app import app
from models import db

with app.app_context():
    try:
        db.engine.execute("""
            CREATE TABLE IF NOT EXISTS admin_activities (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action VARCHAR(255) NOT NULL,
                entity_type VARCHAR(100),
                entity_id INTEGER,
                details TEXT,
                ip_address VARCHAR(45),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(admin_id) REFERENCES users (id)
            )
        """)
        db.engine.execute("CREATE INDEX IF NOT EXISTS ix_admin_activities_admin_id ON admin_activities(admin_id)")
        db.engine.execute("CREATE INDEX IF NOT EXISTS ix_admin_activities_created_at ON admin_activities(created_at)")
        print("Таблица admin_activities успешно создана.")
    except Exception as e:
        print(f"Ошибка: {e}")
