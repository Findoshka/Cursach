"""
Миграция: добавление поля email_verification_token_expires в таблицу users.
"""

import sqlite3
import os

db_path = os.path.join('instance', 'provider.db')

if not os.path.exists(db_path):
    print(f"База данных не найдена: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Проверяем, существует ли поле
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'email_verification_token_expires' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN email_verification_token_expires DATETIME')
        conn.commit()
        print("Поле email_verification_token_expires успешно добавлено.")
    else:
        print("Поле email_verification_token_expires уже существует.")
except Exception as e:
    if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
        print("Поле email_verification_token_expires уже существует.")
    else:
        print(f"Ошибка: {e}")
finally:
    conn.close()
