"""
Откат миграции: удаление поля email_verification_token_expires из таблицы users.
ВНИМАНИЕ: SQLite не поддерживает DROP COLUMN напрямую, поэтому пересоздаем таблицу.
"""

import sqlite3
import os
import shutil
import sys
from datetime import datetime

# Настройка кодировки для Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

db_path = os.path.join('instance', 'provider.db')
backup_path = os.path.join('instance', f'provider_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')

if not os.path.exists(db_path):
    print(f"База данных не найдена: {db_path}")
    exit(1)

# Создаем резервную копию
print(f"Создание резервной копии: {backup_path}")
shutil.copy2(db_path, backup_path)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Проверяем, существует ли поле
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'email_verification_token_expires' in columns:
        print("Удаление поля email_verification_token_expires...")
        
        # Получаем все данные из старой таблицы (без поля email_verification_token_expires)
        cursor.execute("""
            SELECT id, username, password_hash, role, avatar_filename, email, 
                   display_name, email_verified, email_verification_token, created_at 
            FROM users
        """)
        users_data = cursor.fetchall()
        
        # Переименовываем старую таблицу
        cursor.execute("ALTER TABLE users RENAME TO users_old")
        
        # Создаем новую таблицу без поля email_verification_token_expires
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'user' NOT NULL,
                avatar_filename VARCHAR(255),
                email VARCHAR(255) UNIQUE,
                display_name VARCHAR(80),
                email_verified BOOLEAN DEFAULT 0 NOT NULL,
                email_verification_token VARCHAR(255),
                created_at DATETIME
            )
        """)
        
        # Вставляем данные обратно
        cursor.executemany("""
            INSERT INTO users (id, username, password_hash, role, avatar_filename, email, 
                              display_name, email_verified, email_verification_token, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, users_data)
        
        # Удаляем старую таблицу
        cursor.execute("DROP TABLE users_old")
        
        conn.commit()
        print("[OK] Поле email_verification_token_expires успешно удалено.")
        print(f"[OK] Резервная копия сохранена: {backup_path}")
    else:
        print("Поле email_verification_token_expires не существует в таблице users.")
        
except Exception as e:
    print(f"[X] Ошибка: {e}")
    print(f"Восстановление из резервной копии...")
    conn.rollback()
    conn.close()
    if os.path.exists(backup_path):
        shutil.copy2(backup_path, db_path)
        print("[OK] База данных восстановлена из резервной копии.")
    raise
finally:
    conn.close()
