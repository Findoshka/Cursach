"""
Скрипт для очистки базы данных.
ВНИМАНИЕ: Этот скрипт удаляет все данные из базы данных!
"""

from app import app
from models import db, User, Service, Application

with app.app_context():
    # Удаляем все данные
    Application.query.delete()
    Service.query.delete()
    User.query.delete()
    
    db.session.commit()
    print("База данных очищена.")
