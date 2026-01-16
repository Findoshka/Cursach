"""
Модуль авторизации и проверки прав доступа.
"""

from flask import session, redirect, url_for
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from models import User


def hash_password(password):
    """Хэширование пароля."""
    return generate_password_hash(password)


def verify_password(password_hash, password):
    """Проверка пароля."""
    return check_password_hash(password_hash, password)


def login_user(user):
    """Вход пользователя в систему."""
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    session['admin_level'] = user.admin_level if hasattr(user, 'admin_level') else 0
    session['display_name'] = user.get_display_name() if hasattr(user, 'get_display_name') else user.username


def logout_user():
    """Выход пользователя из системы."""
    session.clear()


def get_current_user():
    """Получение текущего пользователя."""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


def require_login(f):
    """Декоратор для проверки авторизации."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """Декоратор для проверки прав администратора."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or user.role != 'admin':
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def require_admin_level(min_level):
    """Декоратор для проверки уровня администратора."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            user = User.query.get(session['user_id'])
            if not user or user.role != 'admin':
                from flask import abort
                abort(403)
            admin_level = user.admin_level or 0
            if admin_level < min_level:
                from flask import abort
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_admin_view(f):
    """Доступ на просмотр админ-разделов."""
    return require_admin_level(1)(f)


def require_admin_edit(f):
    """Доступ на редактирование админ-разделов."""
    return require_admin_level(2)(f)


def require_super_admin(f):
    """Доступ для суперадмина."""
    return require_admin_level(3)(f)
