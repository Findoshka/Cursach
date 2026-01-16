"""
Миграция: добавление таблицы notifications для хранения уведомлений пользователей.
"""
import sqlite3
import os
from datetime import datetime

def migrate():
    db_path = os.path.join('instance', 'provider.db')
    
    if not os.path.exists(db_path):
        print(f"[X] База данных не найдена: {db_path}")
        return
    
    # Создаем backup
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"[OK] Создан backup: {backup_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли таблица
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
        if cursor.fetchone():
            print("[!] Таблица 'notifications' уже существует. Миграция не требуется.")
            conn.close()
            return
        
        # Создаем таблицу notifications
        cursor.execute("""
            CREATE TABLE notifications (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title VARCHAR(500) NOT NULL,
                message TEXT NOT NULL,
                type VARCHAR(50) NOT NULL DEFAULT 'info',
                is_read BOOLEAN NOT NULL DEFAULT 0,
                application_id INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users (id),
                FOREIGN KEY(application_id) REFERENCES applications (id)
            )
        """)
        
        # Создаем индексы для быстрого поиска
        cursor.execute("CREATE INDEX ix_notifications_user_id ON notifications(user_id)")
        cursor.execute("CREATE INDEX ix_notifications_is_read ON notifications(is_read)")
        cursor.execute("CREATE INDEX ix_notifications_created_at ON notifications(created_at)")
        
        conn.commit()
        print("[OK] Таблица 'notifications' успешно создана!")
        print("[OK] Индексы созданы для оптимизации запросов.")
        
    except Exception as e:
        conn.rollback()
        print(f"[X] Ошибка при создании таблицы: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
