"""
Модели базы данных для системы учета заявок провайдера.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Инициализация расширения SQLAlchemy
db = SQLAlchemy()


class Service(db.Model):
    """
    Модель услуги провайдера.
    """
    __tablename__ = 'services'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, comment='Название услуги')
    description = db.Column(db.Text, comment='Описание услуги')
    price = db.Column(db.Float, nullable=False, comment='Цена услуги')
    speed = db.Column(db.String(50), comment='Скорость интернета (если применимо)')
    image_filename = db.Column(db.String(255), comment='Имя файла изображения')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь многие-ко-многим с заявками
    applications = db.relationship('Application', secondary='application_services', back_populates='services')
    
    def __repr__(self):
        return f'<Service {self.name}>'
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'speed': self.speed
        }


class ServiceReview(db.Model):
    """
    Модель отзыва на услугу.
    """
    __tablename__ = 'service_reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False, comment='Оценка 1-5')
    comment = db.Column(db.Text, nullable=True, comment='Комментарий')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('service_id', 'user_id', name='uq_service_reviews_service_user'),
    )
    
    service = db.relationship('Service', backref=db.backref('reviews', lazy=True, cascade='all, delete-orphan'))
    user = db.relationship('User', backref='service_reviews')
    
    def __repr__(self):
        return f'<ServiceReview {self.id} - service {self.service_id} user {self.user_id}>'


class Application(db.Model):
    """
    Модель заявки на подключение услуг.
    """
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(200), nullable=False, comment='Имя клиента')
    client_phone = db.Column(db.String(50), nullable=False, comment='Телефон клиента')
    client_address = db.Column(db.String(500), nullable=False, comment='Адрес подключения')
    status = db.Column(db.String(50), default='новая', nullable=False, comment='Статус заявки')
    notes = db.Column(db.Text, comment='Дополнительные заметки')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sla_deadline = db.Column(db.DateTime, nullable=True, comment='Дедлайн по SLA')
    
    # Связь с пользователем, создавшим заявку
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment='ID пользователя, создавшего заявку')
    user = db.relationship('User', backref='applications')
    
    # Связь многие-ко-многим с услугами
    services = db.relationship('Service', secondary='application_services', back_populates='applications')
    
    def __repr__(self):
        return f'<Application {self.id} - {self.client_name}>'
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        return {
            'id': self.id,
            'client_name': self.client_name,
            'client_phone': self.client_phone,
            'client_address': self.client_address,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'sla_deadline': self.sla_deadline.strftime('%Y-%m-%d %H:%M:%S') if self.sla_deadline else None,
            'services': [s.to_dict() for s in self.services]
        }


# Таблица связи многие-ко-многим между заявками и услугами
application_services = db.Table('application_services',
    db.Column('application_id', db.Integer, db.ForeignKey('applications.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True)
)


class User(db.Model):
    """
    Модель пользователя системы.
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, comment='Имя пользователя')
    password_hash = db.Column(db.String(255), nullable=False, comment='Хэш пароля')
    role = db.Column(db.String(20), default='user', nullable=False, comment='Роль: admin или user')
    admin_level = db.Column(db.Integer, default=0, nullable=False, comment='Уровень администратора: 1=просмотр,2=редактирование,3=суперадмин')
    avatar_filename = db.Column(db.String(255), nullable=True, comment='Имя файла аватара пользователя')
    email = db.Column(db.String(255), nullable=True, unique=True, comment='Email пользователя')
    display_name = db.Column(db.String(80), nullable=True, comment='Отображаемое имя пользователя')
    email_verified = db.Column(db.Boolean, default=False, nullable=False, comment='Подтвержден ли email')
    email_verification_token = db.Column(db.String(255), nullable=True, comment='Токен для подтверждения email')
    email_verification_token_expires = db.Column(db.DateTime, nullable=True, comment='Срок действия токена подтверждения')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def is_admin(self):
        """Проверка, является ли пользователь администратором."""
        return self.role == 'admin'
    
    def get_admin_level_label(self):
        """Человеческое название уровня администратора."""
        if not self.is_admin():
            return None
        return {
            1: 'Просмотр',
            2: 'Редактирование',
            3: 'Суперадмин'
        }.get(self.admin_level, 'Просмотр')

    def get_display_name(self):
        """Получение отображаемого имени пользователя."""
        return self.display_name if self.display_name else self.username


class AdminActivity(db.Model):
    """
    Модель логов действий администратора.
    """
    __tablename__ = 'admin_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False, comment='Тип действия')
    entity_type = db.Column(db.String(100), nullable=True, comment='Тип сущности')
    entity_id = db.Column(db.Integer, nullable=True, comment='ID сущности')
    details = db.Column(db.Text, nullable=True, comment='Дополнительные детали')
    ip_address = db.Column(db.String(45), nullable=True, comment='IP-адрес')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    admin = db.relationship('User', backref='admin_activities')
    
    def __repr__(self):
        return f'<AdminActivity {self.id} - {self.action}>'



class ChatMessage(db.Model):
    """
    Модель сообщения в чате с ИИ-ассистентом.
    """
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_bot = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='chat_messages')
    
    def __repr__(self):
        return f'<ChatMessage {self.id} - {"bot" if self.is_bot else "user"}>'


class SupportTicket(db.Model):
    """
    Модель тикета поддержки.
    """
    __tablename__ = 'support_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), default='новая', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='support_tickets')
    messages = db.relationship('SupportMessage', backref='ticket', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<SupportTicket {self.id} - {self.subject}>'
    
    def get_message_count(self):
        """Получение количества сообщений в тикете."""
        return len(self.messages)


class SupportMessage(db.Model):
    """
    Модель сообщения в тикете поддержки.
    """
    __tablename__ = 'support_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_support = db.Column(db.Boolean, default=False, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='support_messages')
    
    def __repr__(self):
        return f'<SupportMessage {self.id} - {"support" if self.is_support else "user"}>'


class SupportTicketRating(db.Model):
    """
    Модель оценки качества поддержки.
    """
    __tablename__ = 'support_ticket_ratings'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('support_tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False, comment='Оценка 1-5')
    comment = db.Column(db.Text, nullable=True, comment='Комментарий')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('ticket_id', name='uq_support_ticket_ratings_ticket'),
    )
    
    ticket = db.relationship('SupportTicket', backref=db.backref('rating', uselist=False, cascade='all, delete-orphan'))
    user = db.relationship('User', backref='support_ticket_ratings')
    
    def __repr__(self):
        return f'<SupportTicketRating {self.id} - ticket {self.ticket_id}>'


class Notification(db.Model):
    """
    Модель уведомления для пользователя.
    """
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(500), nullable=False, comment='Заголовок уведомления')
    message = db.Column(db.Text, nullable=False, comment='Текст уведомления')
    type = db.Column(db.String(50), default='info', nullable=False, comment='Тип уведомления: info, success, warning, danger')
    is_read = db.Column(db.Boolean, default=False, nullable=False, comment='Прочитано ли уведомление')
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=True, comment='ID связанной заявки (если есть)')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='notifications')
    application = db.relationship('Application', backref='notifications')
    
    def __repr__(self):
        return f'<Notification {self.id} - {self.title}>'
    
    def get_url(self):
        """Получение URL для перехода к связанному объекту."""
        # Если есть application_id - переходим к заявке
        if self.application_id:
            # Возвращаем относительный URL, роль проверим в API
            return f'/applications/{self.application_id}/edit'
        
        # Для тикетов поддержки извлекаем ID из заголовка
        # Формат: "Новое обращение в поддержку #123" или "Новое сообщение в тикете #123" или "Ответ на ваше обращение #123"
        import re
        ticket_match = re.search(r'#(\d+)', self.title)
        if ticket_match:
            ticket_id = ticket_match.group(1)
            return f'/support/ticket/{ticket_id}'
        
        return None
    
    def to_dict(self):
        """Преобразование в словарь для JSON."""
        url = self.get_url()
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'application_id': self.application_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'time_ago': self.get_time_ago(),
            'url': url
        }
    
    def get_time_ago(self):
        """Получение времени в формате 'X минут назад'."""
        delta = datetime.utcnow() - self.created_at
        if delta.days > 0:
            return f'{delta.days} дн. назад'
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f'{hours} ч. назад'
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f'{minutes} мин. назад'
        else:
            return 'только что'