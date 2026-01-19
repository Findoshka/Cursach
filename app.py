"""
Главный файл веб-приложения для учета заявок провайдера.
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, send_from_directory, abort
from flask_mail import Mail, Message
from models import db, Service, Application, User, SupportTicket, SupportMessage, ChatMessage, Notification, ServiceReview, AdminActivity, SupportTicketRating

# Попытка импорта SendGrid для отправки через API
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail as SendGridMail
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

# Попытка импорта Brevo для отправки через API
try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk.rest import ApiException
    BREVO_AVAILABLE = True
except ImportError:
    BREVO_AVAILABLE = False

from ai_assistant import AIAssistant
from auth import login_user, logout_user, get_current_user, require_login, require_admin_view, require_admin_edit, require_super_admin, hash_password, verify_password
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
import secrets
import re

# Попытка импорта python-dotenv для загрузки переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)  # Перезаписываем переменные из .env
except ImportError:
    pass  # python-dotenv не установлен, используем переменные окружения системы

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# База данных: используем DATABASE_URL (Render/Postgres) или SQLite по умолчанию
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///provider.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Максимальный размер файла 16MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Конфигурация ИИ API
app.config['AI_API_BASE_URL'] = os.environ.get('AI_API_BASE_URL', 'https://api.groq.com/openai/v1')
app.config['AI_API_KEY'] = os.environ.get('AI_API_KEY', '')
app.config['AI_MODEL'] = os.environ.get('AI_MODEL', 'llama-3.3-70b-versatile')
app.config['AI_ENABLED'] = os.environ.get('AI_ENABLED', 'true').lower() == 'true'

# SLA настройки
app.config['SLA_DAYS'] = int(os.environ.get('SLA_DAYS', 3))


# Конфигурация почты
# Настройки можно задать через переменные окружения (файл .env) или изменить здесь
# Для Gmail: используйте пароль приложения (не обычный пароль!)
# Инструкции: см. EMAIL_SETUP.md

# Определяем провайдера почты из переменной окружения (gmail, yandex, mailru, mailtrap, sendgrid, brevo)
mail_provider = os.environ.get('MAIL_PROVIDER', 'gmail').lower()

if mail_provider == 'gmail':
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
elif mail_provider == 'yandex':
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.yandex.ru')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USE_SSL'] = True
elif mail_provider == 'mailru':
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.mail.ru')
    # Mail.ru: порт 587 с STARTTLS (рекомендуется) или 465 с SSL
    # Поддержка переменных MAIL_PORT, MAIL_SECURE, MAIL_REQUIRE_TLS
    mail_port = int(os.environ.get('MAIL_PORT', 587))
    mail_secure = os.environ.get('MAIL_SECURE', '').lower() == 'true'
    mail_require_tls = os.environ.get('MAIL_REQUIRE_TLS', '').lower() == 'true'
    
    app.config['MAIL_PORT'] = mail_port
    
    if mail_port == 465:
        # Порт 465: SSL/TLS сразу (implicit TLS)
        app.config['MAIL_USE_TLS'] = False
        app.config['MAIL_USE_SSL'] = True
    elif mail_port == 587:
        # Порт 587: STARTTLS (explicit TLS)
        app.config['MAIL_USE_TLS'] = True
        app.config['MAIL_USE_SSL'] = False
    else:
        # Если указан другой порт, используем настройки из переменных
        app.config['MAIL_USE_TLS'] = mail_require_tls if mail_require_tls else (not mail_secure)
        app.config['MAIL_USE_SSL'] = mail_secure
elif mail_provider == 'mailtrap':
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.mailtrap.io')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 2525))
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
elif mail_provider == 'sendgrid':
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.sendgrid.net')
    # SendGrid поддерживает порты 587 (TLS) и 465 (SSL)
    mail_port = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_PORT'] = mail_port
    
    if mail_port == 465:
        # Порт 465: SSL
        app.config['MAIL_USE_TLS'] = False
        app.config['MAIL_USE_SSL'] = True
    else:
        # Порт 587: TLS (рекомендуется)
        app.config['MAIL_USE_TLS'] = True
        app.config['MAIL_USE_SSL'] = False
    
    # Для SendGrid username всегда "apikey"
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'apikey')
    # Пароль - это API ключ SendGrid
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', '')
elif mail_provider == 'brevo':
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp-relay.brevo.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    # Для Brevo username - это логин, password - это SMTP ключ
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', '')
else:
    # Настройки по умолчанию (Gmail)
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False

# Устанавливаем username, password и sender только если они еще не установлены (для SendGrid и Brevo они уже установлены)
if 'MAIL_USERNAME' not in app.config:
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
if 'MAIL_PASSWORD' not in app.config:
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
if 'MAIL_DEFAULT_SENDER' not in app.config:
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config.get('MAIL_USERNAME', 'noreply@provider.com'))

# Режим отладки: если не настроена почта, выводим ссылки в консоль
# По умолчанию выключен - включите вручную для отладки
app.config['MAIL_DEBUG_MODE'] = os.environ.get('MAIL_DEBUG_MODE', 'false').lower() == 'true'

# Создаем папку для загрузок, если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Инициализация БД
db.init_app(app)

# Инициализация почты
mail = Mail(app)

# Инициализация ИИ-ассистента с настройками API
ai_assistant = AIAssistant(
    api_base_url=app.config.get('AI_API_BASE_URL'),
    api_key=app.config.get('AI_API_KEY'),
    enabled=app.config.get('AI_ENABLED', True),
    model=app.config.get('AI_MODEL')
)


def allowed_file(filename):
    """Проверка расширения файла."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_verification_token():
    """Генерация токена для подтверждения email."""
    return secrets.token_urlsafe(32)


def get_token_expiration():
    """Получение времени истечения токена (60 минут с текущего момента)."""
    return datetime.utcnow() + timedelta(minutes=60)


def get_default_sla_deadline():
    """Дедлайн по SLA по умолчанию."""
    return datetime.utcnow() + timedelta(days=app.config.get('SLA_DAYS', 3))


def parse_sla_deadline(date_str):
    """Парсинг дедлайна из даты (YYYY-MM-DD) с установкой 23:59:59."""
    if not date_str:
        return None
    try:
        date_value = datetime.strptime(date_str, '%Y-%m-%d')
        return date_value + timedelta(hours=23, minutes=59, seconds=59)
    except ValueError:
        return None


def log_admin_action(action, entity_type=None, entity_id=None, details=None):
    """Логирование действий администратора."""
    try:
        current_user = get_current_user()
        if not current_user or not current_user.is_admin():
            return
        
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        
        activity = AdminActivity(
            admin_id=current_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        print(f"[X] Ошибка логирования действия администратора: {e}")



def notify_admins_new_support_ticket(ticket):
    """Создание уведомлений для всех администраторов о новом тикете поддержки."""
    try:
        # Получаем всех администраторов
        admins = User.query.filter(User.role == 'admin', User.admin_level >= 1).all()
        
        if not admins:
            return
        
        # Создаем уведомление для каждого администратора
        for admin in admins:
            notification = Notification(
                user_id=admin.id,
                title=f'Новое обращение в поддержку #{ticket.id}',
                message=f'Пользователь {ticket.user.get_display_name()} создал новое обращение: "{ticket.subject}".',
                type='info'
            )
            db.session.add(notification)
        
        db.session.commit()
        
        print(f"[OK] Уведомления о новом тикете поддержки #{ticket.id} отправлены {len(admins)} администраторам")
    except Exception as e:
        print(f"[X] Ошибка создания уведомлений о тикете для администраторов: {e}")
        import traceback
        traceback.print_exc()


def notify_support_message(message, ticket):
    """Создание уведомлений о новом сообщении в чате поддержки."""
    try:
        # Если сообщение от пользователя - уведомляем администраторов
        if not message.is_support:
            admins = User.query.filter(User.role == 'admin', User.admin_level >= 1).all()
            for admin in admins:
                notification = Notification(
                    user_id=admin.id,
                    title=f'Новое сообщение в тикете #{ticket.id}',
                    message=f'Пользователь {message.user.get_display_name()} написал в обращении "{ticket.subject}": {message.message[:100]}{"..." if len(message.message) > 100 else ""}',
                    type='info'
                )
                db.session.add(notification)
        
        # Если сообщение от администратора - уведомляем пользователя (владельца тикета)
        else:
            if ticket.user_id != message.user_id:  # Не уведомляем администратора о своем же сообщении
                notification = Notification(
                    user_id=ticket.user_id,
                    title=f'Ответ на ваше обращение #{ticket.id}',
                    message=f'Администратор ответил на ваше обращение "{ticket.subject}": {message.message[:100]}{"..." if len(message.message) > 100 else ""}',
                    type='info'
                )
                db.session.add(notification)
        
        db.session.commit()
        
        print(f"[OK] Уведомления о новом сообщении в тикете #{ticket.id} созданы")
    except Exception as e:
        print(f"[X] Ошибка создания уведомлений о сообщении: {e}")
        import traceback
        traceback.print_exc()


def notify_admins_new_application(application):
    """Создание уведомлений для всех администраторов о новой заявке."""
    try:
        # Получаем всех администраторов
        admins = User.query.filter(User.role == 'admin', User.admin_level >= 1).all()
        
        if not admins:
            return
        
        # Список услуг для уведомления
        services_list = ', '.join([s.name for s in application.services]) if application.services else 'Не указано'
        
        # Создаем уведомление для каждого администратора
        for admin in admins:
            notification = Notification(
                user_id=admin.id,
                title=f'Новая заявка #{application.id}',
                message=f'Создана новая заявка от клиента "{application.client_name}" ({application.client_phone}). Адрес: {application.client_address}. Услуги: {services_list}.',
                type='info',
                application_id=application.id
            )
            db.session.add(notification)
        
        db.session.commit()
        
        print(f"[OK] Уведомления о новой заявке #{application.id} отправлены {len(admins)} администраторам")
    except Exception as e:
        print(f"[X] Ошибка создания уведомлений для администраторов: {e}")
        import traceback
        traceback.print_exc()


def send_application_status_email(application, old_status, new_status):
    """Отправка email-уведомления об изменении статуса заявки."""
    # Проверяем, есть ли у заявки связанный пользователь с email
    if not application.user_id or not application.user:
        return False
    
    user = application.user
    if not user.email or not user.email_verified:
        return False
    
    user_email = user.email
    
    # Названия статусов для отображения
    status_names = {
        'новая': 'Новая',
        'в работе': 'В работе',
        'выполнена': 'Выполнена'
    }
    
    status_display = status_names.get(new_status, new_status)
    status_class = new_status.replace(' ', '-').lower()
    
    # Список услуг
    services_list = ', '.join([s.name for s in application.services]) if application.services else 'Не указано'
    
    # URL заявки
    application_url = url_for('my_applications', _external=True)
    
    # Проверяем, какой провайдер используется
    sendgrid_api_key = os.environ.get('SENDGRID_API_KEY', '')
    brevo_api_key = os.environ.get('BREVO_API_KEY', '')
    mail_provider = os.environ.get('MAIL_PROVIDER', '').lower()
    
    # Если используется Brevo через API
    if mail_provider == 'brevo' and brevo_api_key and BREVO_AVAILABLE:
        try:
            import threading
            import time
            
            # Подготавливаем HTML контент ДО создания потока (с контекстом приложения)
            from_email = app.config.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_DEFAULT_SENDER', ''))
            if not from_email:
                print("[X] ОШИБКА: MAIL_DEFAULT_SENDER не установлен для Brevo")
                return False
            
            # Парсим email для имени и адреса
            if '<' in from_email:
                from_name, from_email_addr = from_email.split('<')
                from_name = from_name.strip().strip('"')
                from_email_addr = from_email_addr.strip('>')
            else:
                from_name = "Система учета заявок"
                from_email_addr = from_email
            
            # Рендерим шаблон в контексте приложения
            with app.app_context():
                html_content = render_template(
                    'email_application_status.html',
                    client_name=application.client_name,
                    application_id=application.id,
                    client_phone=application.client_phone,
                    client_address=application.client_address,
                    status_display=status_display,
                    status_class=status_class,
                    services=services_list,
                    notes=application.notes or '',
                    application_url=application_url
                )
            
            # Функция для отправки в отдельном потоке с повторными попытками
            def send_email_thread():
                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    try:
                        configuration = sib_api_v3_sdk.Configuration()
                        configuration.api_key['api-key'] = brevo_api_key
                        configuration.timeout = 15
                        
                        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
                        
                        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                            to=[{"email": user_email}],
                            html_content=html_content,
                            sender={"name": from_name, "email": from_email_addr},
                            subject=f'Изменение статуса заявки #{application.id} - {status_display}'
                        )
                        
                        api_response = api_instance.send_transac_email(send_smtp_email)
                        
                        print(f"[OK] Email-уведомление о статусе заявки #{application.id} отправлено на {user_email}")
                        print(f"     Message ID: {api_response.message_id}")
                        return True
                    except ApiException as e:
                        print(f"[X] Попытка {attempt}/{max_retries}: ОШИБКА отправки уведомления через Brevo API: {e}")
                        if attempt < max_retries:
                            time.sleep(2)
                        else:
                            return False
                    except Exception as e:
                        error_msg = str(e)
                        if ("Connection" in error_msg or "Remote end closed" in error_msg) and attempt < max_retries:
                            print(f"[!] Попытка {attempt}/{max_retries}: Ошибка соединения, повтор через 2 секунды...")
                            time.sleep(2)
                            continue
                        else:
                            if attempt >= max_retries:
                                import traceback
                                traceback.print_exc()
                                return False
                return False
            
            # Запускаем отправку в отдельном потоке
            print(f"[INFO] Запуск отправки email-уведомления о статусе заявки #{application.id} на {user_email}...")
            thread = threading.Thread(target=send_email_thread, daemon=True)
            thread.start()
            return True
            
        except Exception as e:
            print(f"[X] ОШИБКА запуска отправки уведомления: {e}")
            return False
    
    # Режим отладки: если почта не настроена
    if app.config.get('MAIL_DEBUG_MODE') or not app.config.get('MAIL_USERNAME'):
        print("=" * 60)
        print("РЕЖИМ ОТЛАДКИ: Email-уведомление о статусе не отправлено")
        print(f"Заявка #{application.id}: {old_status} -> {new_status}")
        print(f"Email: {user_email}")
        print("=" * 60)
        return True
    
    return False


def send_verification_email(user_email, token):
    """Отправка email с ссылкой для подтверждения."""
    verification_url = url_for('verify_email', token=token, _external=True)
    
    # Проверяем, какой провайдер используется
    sendgrid_api_key = os.environ.get('SENDGRID_API_KEY', '')
    brevo_api_key = os.environ.get('BREVO_API_KEY', '')
    mail_provider = os.environ.get('MAIL_PROVIDER', '').lower()
    
    # Если используется Brevo через API
    if mail_provider == 'brevo' and brevo_api_key and BREVO_AVAILABLE:
        try:
            import threading
            import time
            
            # Подготавливаем HTML контент ДО создания потока (с контекстом приложения)
            from_email = app.config.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_DEFAULT_SENDER', ''))
            if not from_email:
                print("[X] ОШИБКА: MAIL_DEFAULT_SENDER не установлен для Brevo")
                return False
            
            # Парсим email для имени и адреса
            if '<' in from_email:
                from_name, from_email_addr = from_email.split('<')
                from_name = from_name.strip().strip('"')
                from_email_addr = from_email_addr.strip('>')
            else:
                from_name = "Система учета заявок"
                from_email_addr = from_email
            
            # Рендерим шаблон в контексте приложения
            with app.app_context():
                html_content = render_template('email_verification.html', verification_url=verification_url)
            
            # Функция для отправки в отдельном потоке с повторными попытками
            def send_email_thread():
                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    try:
                        configuration = sib_api_v3_sdk.Configuration()
                        configuration.api_key['api-key'] = brevo_api_key
                        # Устанавливаем таймаут для запроса (15 секунд)
                        configuration.timeout = 15
                        
                        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
                        
                        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                            to=[{"email": user_email}],
                            html_content=html_content,
                            sender={"name": from_name, "email": from_email_addr},
                            subject='Подтверждение регистрации - Система учета заявок провайдера'
                        )
                        
                        api_response = api_instance.send_transac_email(send_smtp_email)
                        
                        print(f"[OK] Email успешно отправлен через Brevo API на {user_email}")
                        print(f"     Message ID: {api_response.message_id}")
                        return True
                    except ApiException as e:
                        print(f"[X] Попытка {attempt}/{max_retries}: ОШИБКА отправки через Brevo API: {e}")
                        print(f"     Status Code: {e.status}")
                        print(f"     Reason: {e.reason}")
                        if attempt < max_retries:
                            time.sleep(2)  # Ждем перед повторной попыткой
                        else:
                            print("=" * 60)
                            print(f"Email: {user_email}")
                            print(f"Ссылка для подтверждения: {verification_url}")
                            print("=" * 60)
                            return False
                    except Exception as e:
                        error_msg = str(e)
                        # Если это ошибка соединения, пробуем еще раз
                        if ("Connection" in error_msg or "Remote end closed" in error_msg) and attempt < max_retries:
                            print(f"[!] Попытка {attempt}/{max_retries}: Ошибка соединения, повтор через 2 секунды...")
                            time.sleep(2)
                            continue
                        else:
                            print("=" * 60)
                            print(f"[X] ОШИБКА отправки через Brevo API (попытка {attempt}/{max_retries}): {e}")
                            print(f"Email: {user_email}")
                            print(f"Ссылка для подтверждения: {verification_url}")
                            print("=" * 60)
                            if attempt >= max_retries:
                                import traceback
                                traceback.print_exc()
                                return False
                return False
            
            # Запускаем отправку в отдельном потоке (не блокирует основной запрос)
            print(f"[INFO] Запуск отправки email через Brevo API на {user_email} в фоновом режиме...")
            thread = threading.Thread(target=send_email_thread, daemon=True)
            thread.start()
            
            # Возвращаем True сразу, чтобы не блокировать регистрацию
            # Email будет отправляться в фоне
            return True
            
        except Exception as e:
            print("=" * 60)
            print(f"[X] ОШИБКА запуска отправки через Brevo API: {e}")
            print(f"Email: {user_email}")
            print(f"Ссылка для подтверждения: {verification_url}")
            print("=" * 60)
            return False
    
    # Если используется SendGrid через API
    if mail_provider == 'sendgrid' and sendgrid_api_key and SENDGRID_AVAILABLE:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail as SendGridMail
            
            from_email = app.config.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_DEFAULT_SENDER', ''))
            if not from_email:
                print("[X] ОШИБКА: MAIL_DEFAULT_SENDER не установлен для SendGrid")
                return False
            
            message = SendGridMail(
                from_email=from_email,
                to_emails=user_email,
                subject='Подтверждение регистрации - Система учета заявок провайдера',
                html_content=render_template('email_verification.html', verification_url=verification_url)
            )
            
            sg = SendGridAPIClient(sendgrid_api_key)
            response = sg.send(message)
            
            print(f"[OK] Email успешно отправлен через SendGrid API на {user_email}")
            print(f"     Status Code: {response.status_code}")
            return True
        except Exception as e:
            print("=" * 60)
            print(f"[X] ОШИБКА отправки через SendGrid API: {e}")
            print(f"Email: {user_email}")
            print(f"Ссылка для подтверждения: {verification_url}")
            print("=" * 60)
            import traceback
            traceback.print_exc()
            return False
    
    # Режим отладки: если почта не настроена, выводим ссылку в консоль
    if app.config.get('MAIL_DEBUG_MODE') or not app.config.get('MAIL_USERNAME'):
        print("=" * 60)
        print("РЕЖИМ ОТЛАДКИ: Email не отправлен, ссылка для подтверждения:")
        print(f"Email: {user_email}")
        print(f"Ссылка: {verification_url}")
        print("=" * 60)
        return True
    
    # Реальная отправка email через SMTP (для других провайдеров)
    try:
        msg = Message(
            subject='Подтверждение регистрации - Система учета заявок провайдера',
            recipients=[user_email],
            html=render_template('email_verification.html', verification_url=verification_url),
            sender=app.config['MAIL_DEFAULT_SENDER']
        )
        # Отправка в контексте приложения
        with app.app_context():
            mail.send(msg)
        print(f"[OK] Email успешно отправлен на {user_email}")
        return True
    except Exception as e:
        # Если отправка не удалась, выводим подробную информацию об ошибке
        print("=" * 60)
        print(f"✗ ОШИБКА отправки email: {e}")
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Email получателя: {user_email}")
        print(f"SMTP сервер: {app.config.get('MAIL_SERVER', 'не указан')}")
        print(f"SMTP порт: {app.config.get('MAIL_PORT', 'не указан')}")
        print(f"TLS: {app.config.get('MAIL_USE_TLS', False)}")
        print(f"SSL: {app.config.get('MAIL_USE_SSL', False)}")
        print(f"Отправитель: {app.config.get('MAIL_DEFAULT_SENDER', 'не указан')}")
        print()
        print("Ссылка для подтверждения (можно использовать вручную):")
        print(f"{verification_url}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


def is_valid_email(email):
    """Проверка корректности email адреса."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def init_sample_data():
    """Инициализация БД тестовыми данными."""
    # Создание тестовых услуг
    services = [
        Service(name='Базовый интернет', description='Базовый тариф для дома', price=500, speed='100 Мбит/с'),
        Service(name='Стандартный интернет', description='Стандартный тариф для семьи', price=800, speed='300 Мбит/с'),
        Service(name='Премиум интернет', description='Высокоскоростной интернет', price=1200, speed='500 Мбит/с'),
        Service(name='Интернет + ТВ', description='Интернет и цифровое ТВ', price=1000, speed='300 Мбит/с'),
    ]
    
    for service in services:
        db.session.add(service)
    
    # Создание тестового администратора (логин: admin, пароль: admin)
    if User.query.filter_by(username='admin').first() is None:
        admin = User(
            username='admin',
            password_hash=hash_password('admin'),
            role='admin',
            admin_level=3
        )
        db.session.add(admin)
    
    # Создание тестового пользователя (логин: user, пароль: user)
    if User.query.filter_by(username='user').first() is None:
        user = User(
            username='user',
            password_hash=hash_password('user'),
            role='user',
            display_name=None
        )
        db.session.add(user)
    
    db.session.commit()


# ==================== Главная страница ====================

@app.route('/')
def index():
    """Главная страница."""
    # Если пользователь не авторизован - перенаправляем на вход
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('login'))
    # Все авторизованные пользователи перенаправляются на услуги
    return redirect(url_for('services_list'))


# ==================== Авторизация ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в систему."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Пожалуйста, заполните все обязательные поля.', 'danger')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and verify_password(user.password_hash, password):
            login_user(user)
            flash(f'Добро пожаловать, {user.get_display_name()}!', 'success')
            # Перенаправление в зависимости от роли
            if user.is_admin():
                return redirect(url_for('services_list'))
            else:
                return redirect(url_for('ai_chat'))
        else:
            flash('Неверное имя пользователя или пароль. Проверьте правильность введенных данных.', 'danger')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации (только для обычных пользователей)."""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        if not username or not email or not password or not password_confirm:
            flash('Пожалуйста, заполните все обязательные поля формы.', 'danger')
            return render_template('register.html')
        
        # Проверка корректности email
        if not is_valid_email(email):
            flash('Введите корректный адрес электронной почты.', 'danger')
            return render_template('register.html')
        
        if password != password_confirm:
            flash('Введенные пароли не совпадают. Пожалуйста, повторите попытку.', 'danger')
            return render_template('register.html')
        
        if len(password) < 4:
            flash('Пароль должен содержать минимум 4 символа.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует. Выберите другое имя.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким адресом электронной почты уже зарегистрирован. Воспользуйтесь входом в систему.', 'danger')
            return render_template('register.html')
        
        # Генерация токена для подтверждения email
        verification_token = generate_verification_token()
        token_expires = get_token_expiration()
        
        # Создание нового пользователя (только с ролью user)
        new_user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role='user',
            display_name=None,  # По умолчанию будет использоваться username
            email_verified=False,
            email_verification_token=verification_token,
            email_verification_token_expires=token_expires
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Отправка email с подтверждением (в фоне, не блокирует ответ)
        send_verification_email(email, verification_token)
        
        flash('Регистрация успешно завершена! На ваш адрес электронной почты отправлено письмо с подтверждением. Пожалуйста, проверьте почту (включая папку "Спам") и перейдите по ссылке для активации аккаунта.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/logout')
def logout():
    """Выход из системы."""
    logout_user()
    flash('Вы успешно вышли из системы. До свидания!', 'info')
    return redirect(url_for('login'))


# ==================== Услуги (CRUD) ====================

@app.route('/services')
@require_login
def services_list():
    """Список всех услуг."""
    from sqlalchemy import func
    
    current_user = get_current_user()
    services = Service.query.all()
    
    # Рейтинги услуг
    rating_rows = db.session.query(
        ServiceReview.service_id,
        func.avg(ServiceReview.rating),
        func.count(ServiceReview.id)
    ).group_by(ServiceReview.service_id).all()
    
    ratings = {
        row[0]: {
            'avg': round(float(row[1]), 1) if row[1] is not None else 0,
            'count': int(row[2])
        }
        for row in rating_rows
    }
    
    # Последние отзывы по каждой услуге (до 3)
    reviews_map = {}
    for review in ServiceReview.query.order_by(ServiceReview.created_at.desc()).all():
        reviews_map.setdefault(review.service_id, [])
        if len(reviews_map[review.service_id]) < 3:
            reviews_map[review.service_id].append(review)
    
    # Отзывы текущего пользователя (чтобы подставить в форму)
    user_reviews = {}
    if current_user:
        for review in ServiceReview.query.filter_by(user_id=current_user.id).all():
            user_reviews[review.service_id] = review
    
    return render_template(
        'services.html',
        services=services,
        ratings=ratings,
        reviews_map=reviews_map,
        user_reviews=user_reviews
    )


@app.route('/services/<int:service_id>/review', methods=['POST'])
@require_login
def service_add_review(service_id):
    """Добавление/обновление отзыва на услугу."""
    current_user = get_current_user()
    service = db.session.get(Service, service_id)
    if not service:
        abort(404)
    
    rating = request.form.get('rating', type=int)
    comment = (request.form.get('comment') or '').strip()
    
    if rating not in [1, 2, 3, 4, 5]:
        flash('Пожалуйста, выберите оценку от 1 до 5.', 'danger')
        return redirect(url_for('services_list'))
    
    if len(comment) > 1000:
        flash('Комментарий слишком длинный (максимум 1000 символов).', 'danger')
        return redirect(url_for('services_list'))
    
    existing_review = ServiceReview.query.filter_by(
        service_id=service_id,
        user_id=current_user.id
    ).first()
    
    if existing_review:
        existing_review.rating = rating
        existing_review.comment = comment
        existing_review.updated_at = datetime.utcnow()
        flash('Ваш отзыв обновлен.', 'success')
    else:
        new_review = ServiceReview(
            service_id=service_id,
            user_id=current_user.id,
            rating=rating,
            comment=comment
        )
        db.session.add(new_review)
        flash('Спасибо за ваш отзыв!', 'success')
    
    db.session.commit()
    return redirect(url_for('services_list'))


@app.route('/services/add', methods=['GET', 'POST'])
@require_admin_edit
def service_add():
    """Добавление новой услуги."""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price', 0))
        speed = request.form.get('speed', '')
        
        service = Service(
            name=name,
            description=description,
            price=price,
            speed=speed
        )
        
        # Сначала сохраняем услугу, чтобы получить ID
        db.session.add(service)
        db.session.flush()  # Получаем ID без коммита
        
        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Переименовываем файл с ID услуги
                file_ext = filename.rsplit('.', 1)[1].lower()
                filename = f"service_{service.id}.{file_ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                service.image_filename = filename
        
        db.session.commit()
        
        # Обновляем информацию об услугах в ассистенте
        update_ai_assistant_services()
        
        log_admin_action(
            action='Создание услуги',
            entity_type='service',
            entity_id=service.id,
            details=service.name
        )
        
        return redirect(url_for('services_list'))
    
    return render_template('service_form.html', service=None)


@app.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@require_admin_edit
def service_edit(service_id):
    """Редактирование услуги."""
    service = db.session.get(Service, service_id)
    if not service:
        abort(404)
    
    if request.method == 'POST':
        service.name = request.form.get('name')
        service.description = request.form.get('description')
        service.price = float(request.form.get('price', 0))
        service.speed = request.form.get('speed', '')
        
        # Обработка загрузки нового изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                # Удаляем старое изображение, если есть
                if service.image_filename:
                    old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], service.image_filename)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)
                
                # Сохраняем новое изображение
                filename = secure_filename(file.filename)
                file_ext = filename.rsplit('.', 1)[1].lower()
                filename = f"service_{service.id}.{file_ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                service.image_filename = filename
        
        db.session.commit()
        
        update_ai_assistant_services()
        
        log_admin_action(
            action='Редактирование услуги',
            entity_type='service',
            entity_id=service.id,
            details=service.name
        )
        return redirect(url_for('services_list'))
    
    return render_template('service_form.html', service=service)


@app.route('/services/<int:service_id>/delete', methods=['POST'])
@require_admin_edit
def service_delete(service_id):
    """Удаление услуги."""
    service = db.session.get(Service, service_id)
    if not service:
        abort(404)
    
    service_name = service.name
    
    # Удаляем изображение, если есть
    if service.image_filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], service.image_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    
    db.session.delete(service)
    db.session.commit()
    
    update_ai_assistant_services()
    
    log_admin_action(
        action='Удаление услуги',
        entity_type='service',
        entity_id=service_id,
        details=service_name
    )
    return redirect(url_for('services_list'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Маршрут для отдачи загруженных изображений."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def get_site_logo():
    """Получение имени файла логотипа сайта."""
    logo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'site_logo.png')
    if os.path.exists(logo_path):
        return 'site_logo.png'
    logo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'site_logo.jpg')
    if os.path.exists(logo_path):
        return 'site_logo.jpg'
    return None


@app.route('/admin/logo', methods=['GET', 'POST'])
@require_super_admin
def site_logo_upload():
    """Загрузка/удаление логотипа сайта (только для администраторов)."""
    if request.method == 'POST':
        if 'delete' in request.form:
            # Удаление логотипа
            logo_filename = get_site_logo()
            if logo_filename:
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], logo_filename)
                if os.path.exists(logo_path):
                    os.remove(logo_path)
                    flash('Логотип успешно удален.', 'success')
                    log_admin_action(
                        action='Удаление логотипа',
                        entity_type='site_logo',
                        details=logo_filename
                    )
            return redirect(url_for('site_logo_upload'))
        
        # Загрузка нового логотипа
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '' and allowed_file(file.filename):
                # Удаляем старый логотип
                old_logo = get_site_logo()
                if old_logo:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_logo)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Сохраняем новый логотип
                file_ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"site_logo.{file_ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                flash('Логотип успешно загружен.', 'success')
                log_admin_action(
                    action='Загрузка логотипа',
                    entity_type='site_logo',
                    details=filename
                )
                return redirect(url_for('site_logo_upload'))
            elif file and file.filename != '':
                flash('Недопустимый формат файла. Разрешены: PNG, JPG, JPEG, GIF, WEBP.', 'danger')
    
    site_logo = get_site_logo()
    return render_template('site_logo_upload.html', site_logo=site_logo)


# ==================== Заявки (CRUD) ====================

@app.route('/dashboard')
@require_admin_view
def dashboard():
    """Dashboard для администратора со статистикой."""
    from datetime import datetime, timedelta
    
    # Статистика по заявкам
    total_applications = Application.query.count()
    new_applications = Application.query.filter_by(status='новая').count()
    in_work_applications = Application.query.filter_by(status='в работе').count()
    completed_applications = Application.query.filter_by(status='выполнена').count()
    
    # Статистика за последние 30 дней для графика
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    applications_by_day = []
    for i in range(30):
        day = thirty_days_ago + timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = Application.query.filter(
            Application.created_at >= day,
            Application.created_at < next_day
        ).count()
        applications_by_day.append({
            'date': day.strftime('%d.%m'),
            'count': count
        })
    
    # Статистика по статусам для круговой диаграммы
    status_stats = {
        'Новые': new_applications,
        'В работе': in_work_applications,
        'Выполненные': completed_applications
    }
    
    # Статистика по тикетам поддержки
    total_tickets = SupportTicket.query.count()
    new_tickets = SupportTicket.query.filter_by(status='новая').count()
    in_work_tickets = SupportTicket.query.filter_by(status='в работе').count()
    resolved_tickets = SupportTicket.query.filter_by(status='решена').count()
    closed_tickets = SupportTicket.query.filter_by(status='закрыта').count()
    
    # Общая статистика
    total_users = User.query.count()
    total_services = Service.query.count()
    admin_count = User.query.filter_by(role='admin').count()
    user_count = User.query.filter_by(role='user').count()
    
    # Последние заявки (5)
    recent_applications = Application.query.order_by(Application.created_at.desc()).limit(5).all()
    
    # Последние тикеты (5)
    recent_tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).limit(5).all()
    
    return render_template(
        'dashboard.html',
        total_applications=total_applications,
        new_applications=new_applications,
        in_work_applications=in_work_applications,
        completed_applications=completed_applications,
        applications_by_day=applications_by_day,
        status_stats=status_stats,
        total_tickets=total_tickets,
        new_tickets=new_tickets,
        in_work_tickets=in_work_tickets,
        resolved_tickets=resolved_tickets,
        closed_tickets=closed_tickets,
        total_users=total_users,
        total_services=total_services,
        admin_count=admin_count,
        user_count=user_count,
        recent_applications=recent_applications,
        recent_tickets=recent_tickets
    )


@app.route('/admin/activity')
@require_admin_view
def admin_activity_log():
    """Лог действий администратора."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = AdminActivity.query.order_by(AdminActivity.created_at.desc())
    total = query.count()
    total_pages = (total + per_page - 1) // per_page if total else 1
    
    activities = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return render_template(
        'admin_activity.html',
        activities=activities,
        page=page,
        total_pages=total_pages,
        total=total
    )


@app.route('/admin/users')
@require_super_admin
def admin_users():
    """Управление ролями пользователей (только суперадмин)."""
    from sqlalchemy import or_, func
    
    search_query = request.args.get('search', '').strip()
    query = User.query
    
    if search_query:
        search_lower = search_query.lower()
        search_pattern = f'%{search_lower}%'
        query = query.filter(
            or_(
                func.lower(User.username).like(search_pattern),
                func.lower(User.display_name).like(search_pattern),
                func.lower(User.email).like(search_pattern)
            )
        )
    
    users = query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users, search_query=search_query)


@app.route('/admin/users/<int:user_id>/role', methods=['POST'])
@require_super_admin
def admin_user_update_role(user_id):
    """Обновление роли и уровня администратора."""
    current_user = get_current_user()
    user = db.session.get(User, user_id)
    if not user:
        abort(404)
    
    new_role = request.form.get('role', 'user')
    new_level = request.form.get('admin_level', type=int) or 0
    
    if new_role not in ['user', 'admin']:
        flash('Некорректная роль.', 'danger')
        return redirect(url_for('admin_users'))
    
    # Защита от потери последнего суперадмина
    if user.role == 'admin' and user.admin_level == 3 and (new_role != 'admin' or new_level < 3):
        super_admins_count = User.query.filter(User.role == 'admin', User.admin_level >= 3).count()
        if super_admins_count <= 1:
            flash('Нельзя понизить последнего суперадмина.', 'danger')
            return redirect(url_for('admin_users'))
    
    # Нельзя понизить самого себя ниже суперадмина
    if user.id == current_user.id and (new_role != 'admin' or new_level < 3):
        flash('Нельзя понизить свои права суперадмина.', 'danger')
        return redirect(url_for('admin_users'))
    
    if new_role == 'user':
        user.role = 'user'
        user.admin_level = 0
    else:
        user.role = 'admin'
        user.admin_level = max(1, min(new_level, 3))
    
    db.session.commit()
    if current_user and user.id == current_user.id:
        session['role'] = user.role
        session['admin_level'] = user.admin_level
    flash('Права пользователя обновлены.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/applications')
@require_admin_view
def applications_list():
    """Список всех заявок с поиском и фильтрацией."""
    from sqlalchemy import or_
    
    # Получаем параметры поиска и фильтров
    search_query = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    
    # Начинаем с базового запроса
    query = Application.query
    
    # Улучшенный нестрогий поиск по имени или телефону (регистронезависимый)
    if search_query:
        from sqlalchemy import func
        
        # Нормализуем поисковый запрос: убираем лишние пробелы
        search_normalized = ' '.join(search_query.split())
        search_terms = search_normalized.split() if search_normalized else [search_normalized]
        
        # Собираем все условия поиска
        search_conditions = []
        
        for term in search_terms:
            if not term:
                continue
                
            term_lower = term.lower()
            term_pattern = f'%{term_lower}%'
            
            # Поиск по имени (SQLite не умеет кириллицу в LOWER/NOCASE, поэтому
            # сравниваем напрямую и по возможным регистровым вариантам)
            search_conditions.append(Application.client_name.like(f'%{term}%'))
            search_conditions.append(Application.client_name.like(f'%{term_lower}%'))
            search_conditions.append(Application.client_name.like(f'%{term.upper()}%'))
            search_conditions.append(Application.client_name.like(f'%{term.title()}%'))
            
            # Поиск по телефону (простой LIKE, так как телефоны обычно только цифры)
            search_conditions.append(Application.client_phone.like(f'%{term}%'))
            
            # Поиск по телефону без форматирования (только цифры)
            phone_digits = ''.join(filter(str.isdigit, term))
            if phone_digits and len(phone_digits) >= 3:
                # Очищаем телефон от форматирования при поиске
                phone_cleaned = func.replace(
                    func.replace(
                        func.replace(
                            func.replace(
                                func.replace(Application.client_phone, ' ', ''),
                                '-', ''
                            ),
                            '(', ''
                        ),
                        ')', ''
                    ),
                    '+', ''
                )
                search_conditions.append(phone_cleaned.like(f'%{phone_digits}%'))
        
        # Объединяем все условия через OR (найдется хотя бы одно совпадение)
        if search_conditions:
            query = query.filter(or_(*search_conditions))
    
    # Фильтр по статусу
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    # Фильтр по дате от
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Application.created_at >= date_from_obj)
        except ValueError:
            pass
    
    # Фильтр по дате до
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Добавляем время 23:59:59 для включения всего дня
            date_to_obj = date_to_obj + timedelta(days=1) - timedelta(seconds=1)
            query = query.filter(Application.created_at <= date_to_obj)
        except ValueError:
            pass
    
    # Получаем уникальные статусы для фильтра
    statuses = db.session.query(Application.status).distinct().order_by(Application.status).all()
    status_list = [status[0] for status in statuses]
    
    # Применяем сортировку
    applications = query.order_by(Application.created_at.desc()).all()
    
    return render_template(
        'applications.html',
        applications=applications,
        search_query=search_query,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        statuses=status_list,
        now=datetime.utcnow()
    )


@app.route('/applications/add', methods=['GET', 'POST'])
@require_admin_edit
def application_add():
    """Создание новой заявки."""
    if request.method == 'POST':
        client_name = request.form.get('client_name')
        client_phone = request.form.get('client_phone')
        client_address = request.form.get('client_address')
        notes = request.form.get('notes', '')
        sla_deadline = parse_sla_deadline(request.form.get('sla_deadline', '').strip())
        service_ids = request.form.getlist('service_ids')
        
        # Валидация: проверка выбора услуг
        if not service_ids:
            services = Service.query.all()
            error = "Пожалуйста, выберите хотя бы одну услугу."
            return render_template('application_form.html', application=None, services=services, error=error)
        
        current_user = get_current_user()
        application = Application(
            client_name=client_name,
            client_phone=client_phone,
            client_address=client_address,
            notes=notes,
            status='новая',
            sla_deadline=sla_deadline or get_default_sla_deadline(),
            user_id=current_user.id if current_user else None
        )
        
        # Добавление выбранных услуг
        for service_id in service_ids:
            service = db.session.get(Service, int(service_id))
            if service:
                application.services.append(service)
        
        db.session.add(application)
        db.session.commit()
        
        # Создание уведомлений для администраторов о новой заявке
        notify_admins_new_application(application)
        
        log_admin_action(
            action='Создание заявки',
            entity_type='application',
            entity_id=application.id,
            details=f'{client_name}, {client_phone}'
        )
        
        return redirect(url_for('applications_list'))
    
    services = Service.query.all()
    return render_template('application_form.html', application=None, services=services)


@app.route('/applications/<int:application_id>/edit', methods=['GET', 'POST'])
@require_admin_edit
def application_edit(application_id):
    """Редактирование заявки."""
    application = db.session.get(Application, application_id)
    if not application:
        abort(404)
    
    if request.method == 'POST':
        old_status = application.status  # Сохраняем старый статус
        new_status = request.form.get('status')
        sla_deadline_value = request.form.get('sla_deadline', '').strip()
        
        application.client_name = request.form.get('client_name')
        application.client_phone = request.form.get('client_phone')
        application.client_address = request.form.get('client_address')
        application.status = new_status
        application.notes = request.form.get('notes', '')
        if sla_deadline_value:
            application.sla_deadline = parse_sla_deadline(sla_deadline_value)
        elif application.sla_deadline is None:
            application.sla_deadline = get_default_sla_deadline()
        application.updated_at = datetime.utcnow()
        
        # Обновление услуг
        application.services.clear()
        service_ids = request.form.getlist('service_ids')
        for service_id in service_ids:
            service = db.session.get(Service, int(service_id))
            if service:
                application.services.append(service)
        
        db.session.commit()
        
        # Создание уведомления и отправка email, если статус изменился
        if old_status != new_status:
            # Отправка email-уведомления
            email_sent = send_application_status_email(application, old_status, new_status)
            
            # Создание уведомления на сайте для пользователя
            if application.user_id:
                status_names = {
                    'новая': 'Новая',
                    'в работе': 'В работе',
                    'выполнена': 'Выполнена'
                }
                new_status_display = status_names.get(new_status, new_status)
                old_status_display = status_names.get(old_status, old_status)
                
                notification = Notification(
                    user_id=application.user_id,
                    title=f'Статус заявки #{application.id} изменен',
                    message=f'Статус вашей заявки на подключение услуг изменен с "{old_status_display}" на "{new_status_display}".',
                    type='info',
                    application_id=application.id
                )
                db.session.add(notification)
                db.session.commit()
            if email_sent:
                flash(f'Заявка обновлена. Уведомление о смене статуса ({old_status} → {new_status}) отправлено на email пользователя.', 'success')
            else:
                flash(f'Заявка обновлена. Статус изменен: {old_status} → {new_status}.', 'success')
            
            log_admin_action(
                action='Изменение статуса заявки',
                entity_type='application',
                entity_id=application.id,
                details=f'{old_status} -> {new_status}'
            )
        else:
            flash('Заявка успешно обновлена.', 'success')
            log_admin_action(
                action='Редактирование заявки',
                entity_type='application',
                entity_id=application.id,
                details=application.client_name
            )
        
        return redirect(url_for('applications_list'))
    
    services = Service.query.all()
    return render_template('application_form.html', application=application, services=services)


@app.route('/applications/<int:application_id>/delete', methods=['POST'])
@require_admin_edit
def application_delete(application_id):
    """Удаление заявки."""
    application = db.session.get(Application, application_id)
    if not application:
        abort(404)
    application_name = application.client_name
    db.session.delete(application)
    db.session.commit()
    log_admin_action(
        action='Удаление заявки',
        entity_type='application',
        entity_id=application_id,
        details=application_name
    )
    return redirect(url_for('applications_list'))


# ==================== ИИ-ассистент ====================

@app.route('/profile')
@require_login
def profile():
    """Страница профиля пользователя."""
    current_user = get_current_user()
    # Подсчет статистики
    applications_count = Application.query.filter_by(user_id=current_user.id).count()
    return render_template('profile.html', user=current_user, applications_count=applications_count)


@app.route('/profile/edit', methods=['GET', 'POST'])
@require_login
def profile_edit():
    """Редактирование профиля пользователя."""
    current_user = get_current_user()
    
    if request.method == 'POST':
        # Изменение отображаемого имени (display_name)
        # username (логин) не изменяется - это регистрационные данные
        new_display_name = request.form.get('display_name', '').strip()
        if new_display_name != current_user.get_display_name():
            if len(new_display_name) < 2:
                flash('Отображаемое имя должно содержать минимум 2 символа. Пожалуйста, введите корректное имя.', 'danger')
                return render_template('profile_edit.html', user=current_user)
            
            if len(new_display_name) > 30:
                flash('Отображаемое имя не должно превышать 30 символов. Сократите имя и попробуйте снова.', 'danger')
                return render_template('profile_edit.html', user=current_user)
            
            # Обновление отображаемого имени
            current_user.display_name = new_display_name if new_display_name else None
            # Обновляем отображаемое имя в сессии для удобства
            session['display_name'] = current_user.get_display_name()
            flash('Отображаемое имя успешно обновлено.', 'success')
        
        # Загрузка аватара
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename != '' and allowed_file(file.filename):
                # Удаляем старый аватар, если он есть
                if current_user.avatar_filename:
                    old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], current_user.avatar_filename)
                    if os.path.exists(old_filepath):
                        os.remove(old_filepath)
                
                # Сохраняем новый аватар
                file_ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"avatar_{current_user.id}.{file_ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                current_user.avatar_filename = filename
                flash('Аватар успешно загружен и обновлен.', 'success')
            elif file and file.filename != '':
                flash('Недопустимый формат файла. Пожалуйста, используйте изображения в форматах: PNG, JPG, JPEG, GIF или WEBP.', 'danger')
        
        # Изменение пароля
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if old_password or new_password or confirm_password:
            # Проверка старого пароля
            if not verify_password(current_user.password_hash, old_password):
                flash('Текущий пароль указан неверно. Пожалуйста, проверьте правильность ввода.', 'danger')
                return render_template('profile_edit.html', user=current_user)
            
            # Проверка совпадения новых паролей
            if new_password != confirm_password:
                flash('Новые пароли не совпадают. Убедитесь, что вы правильно ввели пароль в оба поля.', 'danger')
                return render_template('profile_edit.html', user=current_user)
            
            if len(new_password) < 4:
                flash('Пароль должен содержать минимум 4 символа. Выберите более надежный пароль.', 'danger')
                return render_template('profile_edit.html', user=current_user)
            
            # Обновление пароля
            current_user.password_hash = hash_password(new_password)
            flash('Пароль успешно изменен. Используйте новый пароль при следующем входе.', 'success')
        
        db.session.commit()
        return redirect(url_for('profile'))
    
    return render_template('profile_edit.html', user=current_user)


@app.route('/verify-email/<token>')
def verify_email(token):
    """Подтверждение email по токену."""
    user = User.query.filter_by(email_verification_token=token).first()
    
    if not user:
        flash('Ссылка подтверждения недействительна или устарела. Пожалуйста, запросите новую ссылку.', 'danger')
        return redirect(url_for('login'))
    
    if user.email_verified:
        flash('Ваш адрес электронной почты уже подтвержден. Вы можете войти в систему.', 'info')
        return redirect(url_for('login'))
    
    # Проверка срока действия токена
    if user.email_verification_token_expires and user.email_verification_token_expires < datetime.utcnow():
        flash('Срок действия ссылки подтверждения истек. Пожалуйста, запросите новую ссылку для подтверждения.', 'danger')
        return redirect(url_for('resend_verification'))
    
    # Подтверждение email
    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_token_expires = None
    db.session.commit()
    
    flash('Адрес электронной почты успешно подтвержден! Теперь вы можете войти в систему.', 'success')
    return redirect(url_for('login'))


@app.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Повторная отправка письма с подтверждением email."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Пожалуйста, введите адрес электронной почты.', 'danger')
            return render_template('resend_verification.html')
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Не раскрываем информацию о существовании пользователя
            flash('Если указанный адрес электронной почты зарегистрирован в системе, на него будет отправлено письмо с подтверждением.', 'info')
            return render_template('resend_verification.html')
        
        if user.email_verified:
            flash('Этот адрес электронной почты уже подтвержден. Вы можете войти в систему.', 'info')
            return redirect(url_for('login'))
        
        # Генерация нового токена
        verification_token = generate_verification_token()
        token_expires = get_token_expiration()
        
        user.email_verification_token = verification_token
        user.email_verification_token_expires = token_expires
        db.session.commit()
        
        # Отправка email (в фоне, не блокирует ответ)
        send_verification_email(user.email, verification_token)
        
        flash('Письмо с подтверждением отправлено на ваш адрес электронной почты. Пожалуйста, проверьте почту (включая папку "Спам") и перейдите по ссылке для активации аккаунта.', 'success')
        return redirect(url_for('login'))
    
    return render_template('resend_verification.html')


@app.route('/resend-verification/<int:user_id>')
def resend_verification_by_id(user_id):
    """Повторная отправка письма с подтверждением по ID пользователя (для админов)."""
    user = db.session.get(User, user_id)
    
    if not user:
        flash('Пользователь не найден.', 'danger')
        return redirect(url_for('login'))
    
    if user.email_verified:
        flash('Email этого пользователя уже подтвержден.', 'info')
        return redirect(url_for('login'))
    
    # Генерация нового токена
    verification_token = generate_verification_token()
    
    user.email_verification_token = verification_token
    db.session.commit()
    
    # Отправка email (в фоне, не блокирует ответ)
    send_verification_email(user.email, verification_token)
    
    flash('Письмо с подтверждением отправлено на ваш email. Пожалуйста, проверьте почту (включая папку "Спам").', 'success')
    return redirect(url_for('login'))


@app.route('/my-applications')
@require_login
def my_applications():
    """Список заявок текущего пользователя."""
    current_user = get_current_user()
    applications = Application.query.filter_by(user_id=current_user.id).order_by(Application.created_at.desc()).all()
    return render_template('my_applications.html', applications=applications, now=datetime.utcnow())


@app.route('/buy-service', methods=['POST'])
@require_login
def buy_service():
    """Оформление заявки на покупку услуги."""
    service_id = request.form.get('service_id')
    client_name = request.form.get('client_name')
    client_phone = request.form.get('client_phone')
    client_address = request.form.get('client_address')
    notes = request.form.get('notes', '')
    
    if not all([service_id, client_name, client_phone, client_address]):
        flash('Пожалуйста, заполните все обязательные поля.', 'danger')
        return redirect(url_for('services_list'))
    
    service = db.session.get(Service, int(service_id))
    if not service:
        flash('Услуга не найдена.', 'danger')
        return redirect(url_for('services_list'))
    
    current_user = get_current_user()
    application = Application(
        client_name=client_name,
        client_phone=client_phone,
        client_address=client_address,
        notes=notes or f'Заявка на услугу: {service.name}',
        status='новая',
        sla_deadline=get_default_sla_deadline(),
        user_id=current_user.id if current_user else None
    )
    
    application.services.append(service)
    db.session.add(application)
    db.session.commit()
    
    # Создание уведомлений для администраторов о новой заявке
    notify_admins_new_application(application)
    
    flash(f'Заявка на услугу "{service.name}" успешно оформлена! Наш менеджер свяжется с вами в ближайшее время для уточнения деталей подключения.', 'success')
    return redirect(url_for('my_applications'))


# ==================== Поддержка ====================

@app.route('/support')
@require_login
def support_chat():
    """Список тикетов поддержки."""
    current_user = get_current_user()
    status_filter = request.args.get('status', '').strip()
    
    if current_user.is_admin():
        # Администратор видит все тикеты
        query = SupportTicket.query
    else:
        # Пользователь видит только свои тикеты
        query = SupportTicket.query.filter_by(user_id=current_user.id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    tickets = query.order_by(SupportTicket.updated_at.desc()).all()
    statuses = db.session.query(SupportTicket.status).distinct().order_by(SupportTicket.status).all()
    status_list = [status[0] for status in statuses]
    
    return render_template('support_chat.html', tickets=tickets, statuses=status_list, status_filter=status_filter)


@app.route('/support/ticket/create', methods=['GET', 'POST'])
@require_login
def support_ticket_create():
    """Создание нового тикета поддержки."""
    current_user = get_current_user()
    
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        
        if not subject or not message:
            flash('Заполните все поля.', 'danger')
            return render_template('support_ticket_create.html')
        
        # Создание тикета
        ticket = SupportTicket(
            user_id=current_user.id,
            subject=subject,
            status='новая'
        )
        db.session.add(ticket)
        db.session.flush()
        
        # Создание первого сообщения
        support_message = SupportMessage(
            ticket_id=ticket.id,
            user_id=current_user.id,
            message=message,
            is_support=False
        )
        db.session.add(support_message)
        db.session.commit()
        
        # Создание уведомлений для администраторов о новом тикете
        notify_admins_new_support_ticket(ticket)
        
        flash('Тикет успешно создан!', 'success')
        return redirect(url_for('support_ticket', ticket_id=ticket.id))
    
    return render_template('support_ticket_create.html')


@app.route('/support/ticket/<int:ticket_id>')
@require_login
def support_ticket(ticket_id):
    """Просмотр тикета поддержки."""
    current_user = get_current_user()
    ticket = db.session.get(SupportTicket, ticket_id)
    
    if not ticket:
        abort(404)
    
    # Проверка доступа
    if not current_user.is_admin() and ticket.user_id != current_user.id:
        abort(403)
    
    messages = SupportMessage.query.filter_by(ticket_id=ticket_id).order_by(SupportMessage.created_at.asc()).all()
    rating = SupportTicketRating.query.filter_by(ticket_id=ticket_id).first()
    
    return render_template('support_ticket.html', ticket=ticket, messages=messages, rating=rating)


@app.route('/support/ticket/<int:ticket_id>/message', methods=['POST'])
@require_login
def support_ticket_message(ticket_id):
    """Отправка сообщения в тикет."""
    current_user = get_current_user()
    ticket = db.session.get(SupportTicket, ticket_id)
    
    if not ticket:
        return jsonify({'error': 'Тикет не найден'}), 404
    
    # Проверка доступа
    if not current_user.is_admin() and ticket.user_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    message_text = request.form.get('message', '').strip()
    if not message_text:
        return jsonify({'error': 'Сообщение не может быть пустым'}), 400
    
    # Обработка загрузки изображения
    image_filename = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '' and allowed_file(file.filename):
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            image_filename = f"support_{ticket_id}_{datetime.utcnow().timestamp()}.{file_ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            file.save(filepath)
    
    # Создание сообщения
    is_support = current_user.is_admin()
    support_message = SupportMessage(
        ticket_id=ticket_id,
        user_id=current_user.id,
        message=message_text,
        is_support=is_support,
        image_filename=image_filename
    )
    db.session.add(support_message)
    
    # Обновление времени тикета
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    
    # Создание уведомлений о новом сообщении
    notify_support_message(support_message, ticket)
    
    return jsonify({
        'success': True,
        'message': {
            'id': support_message.id,
            'message': support_message.message,
            'is_support': support_message.is_support,
            'image_filename': support_message.image_filename,
            'created_at': support_message.created_at.strftime('%d.%m.%Y %H:%M')
        }
    })


@app.route('/support/ticket/<int:ticket_id>/rate', methods=['POST'])
@require_login
def support_ticket_rate(ticket_id):
    """Оценка качества поддержки."""
    current_user = get_current_user()
    ticket = db.session.get(SupportTicket, ticket_id)
    
    if not ticket:
        abort(404)
    
    if current_user.is_admin() or ticket.user_id != current_user.id:
        abort(403)
    
    if ticket.status not in ['решена', 'закрыта']:
        flash('Оценка доступна только после решения или закрытия тикета.', 'warning')
        return redirect(url_for('support_ticket', ticket_id=ticket_id))
    
    rating_value = request.form.get('rating', type=int)
    comment = (request.form.get('comment') or '').strip()
    
    if rating_value not in [1, 2, 3, 4, 5]:
        flash('Пожалуйста, выберите оценку от 1 до 5.', 'danger')
        return redirect(url_for('support_ticket', ticket_id=ticket_id))
    
    if len(comment) > 1000:
        flash('Комментарий слишком длинный (максимум 1000 символов).', 'danger')
        return redirect(url_for('support_ticket', ticket_id=ticket_id))
    
    existing = SupportTicketRating.query.filter_by(ticket_id=ticket_id).first()
    if existing:
        if existing.user_id != current_user.id:
            abort(403)
        existing.rating = rating_value
        existing.comment = comment
        existing.updated_at = datetime.utcnow()
        flash('Спасибо! Ваша оценка обновлена.', 'success')
    else:
        new_rating = SupportTicketRating(
            ticket_id=ticket_id,
            user_id=current_user.id,
            rating=rating_value,
            comment=comment
        )
        db.session.add(new_rating)
        flash('Спасибо за вашу оценку!', 'success')
    
    db.session.commit()
    return redirect(url_for('support_ticket', ticket_id=ticket_id))


@app.route('/support/ticket/<int:ticket_id>/status', methods=['POST'])
@require_admin_edit
def support_ticket_status(ticket_id):
    """Изменение статуса тикета (только для администраторов)."""
    ticket = db.session.get(SupportTicket, ticket_id)
    
    if not ticket:
        return jsonify({'error': 'Тикет не найден'}), 404
    
    new_status = request.json.get('status')
    if new_status not in ['новая', 'в работе', 'решена', 'закрыта']:
        return jsonify({'error': 'Неверный статус'}), 400
    
    ticket.status = new_status
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    
    log_admin_action(
        action='Изменение статуса тикета',
        entity_type='support_ticket',
        entity_id=ticket.id,
        details=new_status
    )
    
    return jsonify({'success': True, 'status': new_status})


# ==================== ИИ-ассистент ====================

@app.route('/ai-chat')
@require_login
def ai_chat():
    """Страница чата с ИИ-ассистентом."""
    # Инициализация сессии для чата
    if 'chat_session_id' not in session:
        session['chat_session_id'] = f"session_{datetime.utcnow().timestamp()}"
    
    # Обновляем информацию об услугах в ассистенте
    update_ai_assistant_services()
    
    # Передаем роль пользователя в шаблон
    current_user = get_current_user()
    is_admin = current_user.is_admin() if current_user else False
    
    # Загружаем историю чата
    session_id = session['chat_session_id']
    chat_history = ChatMessage.query.filter_by(
        user_id=current_user.id,
        session_id=session_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    # Если истории нет, пытаемся найти последнюю активную сессию
    if not chat_history:
        last_message = ChatMessage.query.filter_by(
            user_id=current_user.id
        ).order_by(ChatMessage.created_at.desc()).first()
        
        if last_message:
            session['chat_session_id'] = last_message.session_id
            chat_history = ChatMessage.query.filter_by(
                user_id=current_user.id,
                session_id=last_message.session_id
            ).order_by(ChatMessage.created_at.asc()).all()
    
    return render_template('ai_chat.html', is_admin=is_admin, chat_history=chat_history)


@app.route('/ai-chat/message', methods=['POST'])
@require_login
def ai_chat_message():
    """Обработка сообщения в чате с ИИ-ассистентом."""
    if 'chat_session_id' not in session:
        session['chat_session_id'] = f"session_{datetime.utcnow().timestamp()}"
    
    user_message = request.json.get('message', '')
    session_id = session['chat_session_id']
    current_user = get_current_user()
    
    # Сохранение сообщения пользователя
    try:
        user_chat_message = ChatMessage(
            user_id=current_user.id,
            session_id=session_id,
            message=user_message,
            is_bot=False
        )
        db.session.add(user_chat_message)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка сохранения сообщения пользователя: {e}")
    
    # Получаем ответ от ассистента
    response = ai_assistant.process_message(user_message, session_id)
    
    # Сохранение ответа бота
    try:
        bot_chat_message = ChatMessage(
            user_id=current_user.id,
            session_id=session_id,
            message=response,
            is_bot=True
        )
        db.session.add(bot_chat_message)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка сохранения сообщения бота: {e}")
    
    # Проверяем, готова ли заявка к созданию
    application_data = ai_assistant.get_application_data(session_id)
    
    return jsonify({
        'response': response,
        'application_ready': application_data is not None and 
                           ai_assistant.conversation_context.get(session_id, {}).get('step') == 'application_confirmed'
    })


@app.route('/ai-chat/history', methods=['GET'])
@require_login
def ai_chat_history():
    """Получение истории чата."""
    if 'chat_session_id' not in session:
        session['chat_session_id'] = f"session_{datetime.utcnow().timestamp()}"
    
    session_id = session['chat_session_id']
    current_user = get_current_user()
    
    # Получаем историю для текущей сессии
    chat_history = ChatMessage.query.filter_by(
        user_id=current_user.id,
        session_id=session_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    # Если истории нет, пытаемся найти последнюю активную сессию
    if not chat_history:
        last_message = ChatMessage.query.filter_by(
            user_id=current_user.id
        ).order_by(ChatMessage.created_at.desc()).first()
        
        if last_message:
            session['chat_session_id'] = last_message.session_id
            chat_history = ChatMessage.query.filter_by(
                user_id=current_user.id,
                session_id=last_message.session_id
            ).order_by(ChatMessage.created_at.asc()).all()
    
    return jsonify({
        'history': [
            {
                'message': msg.message,
                'is_bot': msg.is_bot,
                'created_at': msg.created_at.strftime('%d.%m.%Y %H:%M')
            }
            for msg in chat_history
        ]
    })


@app.route('/ai-chat/create-application', methods=['POST'])
@require_login
def ai_chat_create_application():
    """Создание заявки из данных ИИ-ассистента."""
    if 'chat_session_id' not in session:
        return jsonify({'error': 'Сессия не найдена'}), 400
    
    session_id = session['chat_session_id']
    application_data = ai_assistant.get_application_data(session_id)
    
    if not application_data:
        return jsonify({'error': 'Данные заявки не найдены'}), 400
    
    # Создание заявки
    current_user = get_current_user()
    application = Application(
        client_name=application_data.get('client_name'),
        client_phone=application_data.get('client_phone'),
        client_address=application_data.get('client_address'),
        status='новая',
        notes='Создано через ИИ-ассистента',
        sla_deadline=get_default_sla_deadline(),
        user_id=current_user.id if current_user else None
    )
    
    # Добавление услуг
    service_ids = application_data.get('service_ids', [])
    for service_id in service_ids:
        service = db.session.get(Service, service_id)
        if service:
            application.services.append(service)
    
    db.session.add(application)
    db.session.commit()
    
    # Создание уведомлений для администраторов о новой заявке
    notify_admins_new_application(application)
    
    # Очистка сессии
    ai_assistant.clear_session(session_id)
    
    return jsonify({'success': True, 'application_id': application.id})


def update_ai_assistant_services():
    """Обновление информации об услугах в ИИ-ассистенте."""
    services = Service.query.all()
    services_data = [s.to_dict() for s in services]
    ai_assistant.set_services(services_data)


@app.context_processor
def inject_user():
    """Добавляет информацию о текущем пользователе во все шаблоны."""
    user = get_current_user()
    site_logo = get_site_logo()
    unread_notifications_count = 0
    if user:
        # Синхронизируем сессию с актуальной ролью
        session['role'] = user.role
        session['admin_level'] = user.admin_level
        unread_notifications_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        return dict(current_user=user, site_logo=site_logo, unread_notifications_count=unread_notifications_count)
    return dict(current_user=None, site_logo=site_logo, unread_notifications_count=0)


# Инициализация данных об услугах при старте
with app.app_context():
    db.create_all()
    
    # Создание тестовых пользователей, если их нет
    if User.query.filter_by(username='admin').first() is None:
        admin = User(
            username='admin',
            password_hash=hash_password('admin'),
            role='admin',
            admin_level=3,
            display_name=None  # По умолчанию будет использоваться username
        )
        db.session.add(admin)
        db.session.commit()
        print("Создан администратор: admin/admin")
    
    if User.query.filter_by(username='user').first() is None:
        user = User(
            username='user',
            password_hash=hash_password('user'),
            role='user',
            display_name=None  # По умолчанию будет использоваться username
        )
        db.session.add(user)
        db.session.commit()
        print("Создан пользователь: user/user")
    
    # Создание тестовых услуг, если их нет
    if Service.query.count() == 0:
        services = [
            Service(name='Базовый интернет', description='Базовый тариф для дома', price=500, speed='100 Мбит/с'),
            Service(name='Стандартный интернет', description='Стандартный тариф для семьи', price=800, speed='300 Мбит/с'),
            Service(name='Премиум интернет', description='Высокоскоростной интернет', price=1200, speed='500 Мбит/с'),
            Service(name='Интернет + ТВ', description='Интернет и цифровое ТВ', price=1000, speed='300 Мбит/с'),
        ]
        for service in services:
            db.session.add(service)
        db.session.commit()
        print("Созданы тестовые услуги")
    
    update_ai_assistant_services()


# ==================== Уведомления ====================

@app.route('/api/notifications', methods=['GET'])
@require_login
def get_notifications():
    """Получение списка уведомлений текущего пользователя."""
    current_user = get_current_user()
    limit = request.args.get('limit', 20, type=int)
    
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .limit(limit)\
        .all()
    
    # Преобразуем уведомления с корректировкой URL для заявок
    notifications_data = []
    for n in notifications:
        notif_dict = n.to_dict()
        # Для заявок: если пользователь не админ, показываем список заявок
        if notif_dict.get('application_id') and not current_user.is_admin():
            notif_dict['url'] = url_for('my_applications')
        notifications_data.append(notif_dict)
    
    return jsonify({
        'notifications': notifications_data,
        'unread_count': Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    })


@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@require_login
def mark_notification_read(notification_id):
    """Отметить уведомление как прочитанное."""
    current_user = get_current_user()
    notification = Notification.query.get(notification_id)
    
    if not notification or notification.user_id != current_user.id:
        return jsonify({'error': 'Уведомление не найдено'}), 404
    
    notification.is_read = True
    db.session.commit()
    
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    
    return jsonify({
        'success': True,
        'unread_count': unread_count
    })


@app.route('/api/notifications/read-all', methods=['POST'])
@require_login
def mark_all_notifications_read():
    """Отметить все уведомления как прочитанные."""
    current_user = get_current_user()
    
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    
    return jsonify({
        'success': True,
        'unread_count': 0
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
