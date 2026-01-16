"""
Скрипт для очистки email-данных пользователей в базе данных.
Очищает поля: email, email_verified, email_verification_token, email_verification_token_expires
Это позволит заново зарегистрироваться с теми же email адресами.
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
    # Получаем количество пользователей с email
    cursor.execute("SELECT COUNT(*) FROM users WHERE email IS NOT NULL")
    count = cursor.fetchone()[0]
    
    print(f"Найдено пользователей с email: {count}")
    
    if count == 0:
        print("Нет пользователей с email для очистки.")
        conn.close()
        exit(0)
    
    # Показываем список email адресов перед очисткой
    cursor.execute("SELECT id, username, email FROM users WHERE email IS NOT NULL")
    users = cursor.fetchall()
    
    print("\nСписок пользователей с email:")
    for user_id, username, email in users:
        print(f"  ID: {user_id}, Username: {username}, Email: {email}")
    
    # Проверяем аргумент командной строки для автоматического выполнения
    auto_confirm = len(sys.argv) > 1 and sys.argv[1].lower() == '--yes'
    
    if not auto_confirm:
        # Подтверждение
        response = input(f"\nОчистить email-данные у {count} пользователей? (yes/no): ").strip().lower()
    else:
        response = 'yes'
        print(f"\nАвтоматическая очистка email-данных у {count} пользователей...")
    
    if response == 'yes':
        # Очищаем email-связанные поля
        cursor.execute("""
            UPDATE users 
            SET email = NULL,
                email_verified = 0,
                email_verification_token = NULL,
                email_verification_token_expires = NULL
            WHERE email IS NOT NULL
        """)
        
        conn.commit()
        
        print(f"\n[OK] Email-данные успешно очищены у {count} пользователей.")
        print(f"[OK] Резервная копия сохранена: {backup_path}")
        print("\nТеперь можно заново зарегистрироваться с теми же email адресами.")
    else:
        print("Операция отменена.")
        
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
