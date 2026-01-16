"""
Миграция: добавление поля sla_deadline в таблицу applications.
"""

import sqlite3
import os
from datetime import datetime

SLA_DAYS = 3

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
        cursor.execute("PRAGMA table_info(applications)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'sla_deadline' in columns:
            print("[!] Колонка sla_deadline уже существует.")
        else:
            cursor.execute("ALTER TABLE applications ADD COLUMN sla_deadline DATETIME")
            print("[OK] Колонка sla_deadline добавлена.")
        
        cursor.execute(
            "UPDATE applications SET sla_deadline = datetime(created_at, ?)"
            " WHERE sla_deadline IS NULL AND created_at IS NOT NULL",
            (f'+{SLA_DAYS} days',)
        )
        print("[OK] Дедлайны по SLA рассчитаны для существующих заявок.")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[X] Ошибка: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
