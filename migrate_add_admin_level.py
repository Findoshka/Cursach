"""
Миграция: добавление поля admin_level в таблицу users.
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
        # Проверяем, есть ли колонка
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'admin_level' in columns:
            print("[!] Колонка admin_level уже существует.")
        else:
            cursor.execute("ALTER TABLE users ADD COLUMN admin_level INTEGER NOT NULL DEFAULT 0")
            print("[OK] Колонка admin_level добавлена.")
        
        # Обновляем уровни
        cursor.execute("UPDATE users SET admin_level = 2 WHERE role = 'admin' AND admin_level = 0")
        cursor.execute("UPDATE users SET admin_level = 3 WHERE username = 'admin'")
        print("[OK] Уровни администраторов обновлены.")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[X] Ошибка: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
