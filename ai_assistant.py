"""
Модуль ИИ-ассистента для консультаций и создания заявок.
"""

import requests
import json


class AIAssistant:
    """Класс для работы с ИИ-ассистентом."""
    
    def __init__(self, api_base_url=None, api_key=None, enabled=True):
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.enabled = enabled
        self.services = []
        self.conversation_context = {}
        self.conversation_history = {}
    
    def set_services(self, services_data):
        """Установка списка услуг."""
        self.services = services_data
    
    def process_message(self, user_message, session_id):
        """Обработка сообщения пользователя."""
        # Инициализация контекста для сессии
        if session_id not in self.conversation_context:
            self.conversation_context[session_id] = {
                'step': 'greeting',
                'application_data': {}
            }
        
        # Добавляем сообщение в историю
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        
        self.conversation_history[session_id].append({
            'role': 'user',
            'content': user_message
        })
        
        # Ограничиваем историю последними 20 сообщениями
        if len(self.conversation_history[session_id]) > 20:
            self.conversation_history[session_id] = self.conversation_history[session_id][-20:]
        
        context = self.conversation_context[session_id]
        message_lower = user_message.lower()
        
        # Проверяем, начался ли процесс оформления заявки
        if any(word in message_lower for word in ['оформить', 'заявка', 'подключить', 'application']) and context['step'] == 'greeting':
            context['step'] = 'application_name'
            response = "Отлично! Давайте оформим заявку. Начнем с вашего имени. Как вас зовут?"
            self.conversation_history[session_id].append({
                'role': 'assistant',
                'content': response
            })
            return response
        
        # Поэтапный сбор данных заявки
        if context['step'] == 'application_name':
            context['application_data']['client_name'] = user_message.strip()
            context['step'] = 'application_phone'
            response = f"Приятно познакомиться, {user_message.strip()}! Теперь укажите ваш номер телефона (например: +7 (999) 123-45-67)."
            self.conversation_history[session_id].append({
                'role': 'assistant',
                'content': response
            })
            return response
        
        if context['step'] == 'application_phone':
            context['application_data']['client_phone'] = user_message.strip()
            context['step'] = 'application_address'
            response = "Спасибо! Теперь укажите адрес подключения (город, улица, дом)."
            self.conversation_history[session_id].append({
                'role': 'assistant',
                'content': response
            })
            return response
        
        if context['step'] == 'application_address':
            context['application_data']['client_address'] = user_message.strip()
            context['step'] = 'application_service'
            if self.services:
                services_text = "\n".join([f"{i+1}. {s['name']} - {s['price']} руб./мес." for i, s in enumerate(self.services)])
                response = f"Отлично! Теперь выберите услугу (укажите номер):\n\n{services_text}"
            else:
                response = "К сожалению, услуги временно недоступны."
            self.conversation_history[session_id].append({
                'role': 'assistant',
                'content': response
            })
            return response
        
        if context['step'] == 'application_service':
            try:
                service_num = int(user_message.strip())
                if 1 <= service_num <= len(self.services):
                    selected_service = self.services[service_num - 1]
                    context['application_data']['service_ids'] = [selected_service['id']]
                    context['step'] = 'application_confirmed'
                    response = f"Отлично! Вы выбрали услугу: {selected_service['name']}.\n\nПроверьте данные:\n• Имя: {context['application_data'].get('client_name')}\n• Телефон: {context['application_data'].get('client_phone')}\n• Адрес: {context['application_data'].get('client_address')}\n• Услуга: {selected_service['name']}\n\nЗаявка готова к созданию. Нажмите кнопку «Создать заявку»."
                else:
                    response = f"Пожалуйста, укажите номер услуги от 1 до {len(self.services)}."
            except ValueError:
                response = "Пожалуйста, укажите номер услуги цифрой."
            
            self.conversation_history[session_id].append({
                'role': 'assistant',
                'content': response
            })
            return response
        
        # Если не в процессе оформления заявки, используем API или простые ответы
        if self.enabled and self.api_base_url and self.api_key:
            try:
                response = self._call_api(user_message, session_id)
                # Добавляем ответ в историю
                self.conversation_history[session_id].append({
                    'role': 'assistant',
                    'content': response
                })
                return response
            except Exception as e:
                print(f"Ошибка API: {e}")
                # Fallback на простые ответы
                response = self._simple_response(user_message, session_id)
                self.conversation_history[session_id].append({
                    'role': 'assistant',
                    'content': response
                })
                return response
        else:
            # Простые ответы без API
            response = self._simple_response(user_message, session_id)
            # Добавляем ответ в историю
            self.conversation_history[session_id].append({
                'role': 'assistant',
                'content': response
            })
            return response
    
    def _call_api(self, user_message, session_id):
        """Вызов реального API."""
        url = f"{self.api_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Формируем промпт с информацией об услугах
        services_text = "\n".join([f"- {s['name']}: {s.get('description', '')} - {s['price']} руб./мес." for s in self.services])
        
        system_prompt = f"""Ты ИИ-ассистент интернет-провайдера. Помогай пользователям узнать об услугах и оформить заявку на подключение.

Доступные услуги:
{services_text}

Твоя задача:
1. Консультировать по услугам
2. Помогать оформить заявку (собирать: имя, телефон, адрес, выбор услуг)
3. Быть вежливым и дружелюбным

Отвечай кратко и по делу."""
        
        # Получаем историю разговора
        messages = [{"role": "system", "content": system_prompt}]
        if session_id in self.conversation_history:
            # Берем последние 10 сообщений из истории
            recent_history = self.conversation_history[session_id][-10:]
            for msg in recent_history:
                messages.append({
                    "role": msg['role'],
                    "content": msg['content']
                })
        
        messages.append({"role": "user", "content": user_message})
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        return result['choices'][0]['message']['content']
    
    def _simple_response(self, user_message, session_id):
        """Простые ответы без API."""
        message_lower = user_message.lower()
        
        # Инициализация контекста для сессии
        if session_id not in self.conversation_context:
            self.conversation_context[session_id] = {
                'step': 'greeting',
                'application_data': {}
            }
        
        context = self.conversation_context[session_id]
        
        # Приветствие
        if any(word in message_lower for word in ['привет', 'здравствуй', 'добрый', 'hello', 'hi']):
            context['step'] = 'greeting'
            return "Привет! Чем могу помочь? Если у вас есть вопросы о наших тарифах или услугах, дайте знать. Если хотите оформить заявку, просто напишите «оформить заявку»."
        
        # Список услуг
        if any(word in message_lower for word in ['услуги', 'тарифы', 'тариф', 'service', 'services']):
            if self.services:
                services_text = "\n".join([f"• {s['name']}: {s.get('description', '')} - {s['price']} руб./мес." for s in self.services])
                return f"Вот наши услуги:\n\n{services_text}\n\nХотите оформить заявку на одну из них?"
            else:
                return "К сожалению, услуги временно недоступны."
        
        # Оформление заявки
        if any(word in message_lower for word in ['оформить', 'заявка', 'подключить', 'application']):
            context['step'] = 'application_name'
            return "Отлично! Давайте оформим заявку. Начнем с вашего имени. Как вас зовут?"
        
        # Сбор данных заявки
        if context['step'] == 'application_name':
            context['application_data']['client_name'] = user_message
            context['step'] = 'application_phone'
            return f"Приятно познакомиться, {user_message}! Теперь укажите ваш номер телефона."
        
        if context['step'] == 'application_phone':
            context['application_data']['client_phone'] = user_message
            context['step'] = 'application_address'
            return "Спасибо! Теперь укажите адрес подключения."
        
        if context['step'] == 'application_address':
            context['application_data']['client_address'] = user_message
            context['step'] = 'application_service'
            services_text = "\n".join([f"{i+1}. {s['name']}" for i, s in enumerate(self.services)])
            return f"Отлично! Теперь выберите услугу (укажите номер):\n\n{services_text}"
        
        if context['step'] == 'application_service':
            try:
                service_num = int(user_message.strip())
                if 1 <= service_num <= len(self.services):
                    selected_service = self.services[service_num - 1]
                    context['application_data']['service_ids'] = [selected_service['id']]
                    context['step'] = 'application_confirmed'
                    return f"Отлично! Вы выбрали услугу: {selected_service['name']}. Заявка готова к созданию. Нажмите кнопку «Создать заявку»."
                else:
                    return "Пожалуйста, укажите номер услуги из списка."
            except ValueError:
                return "Пожалуйста, укажите номер услуги."
        
        # Общие ответы
        return "Извините, я не понял ваш вопрос. Могу помочь с информацией об услугах или оформлением заявки. Напишите «услуги» или «оформить заявку»."
    
    def get_application_data(self, session_id):
        """Получение данных заявки из контекста."""
        if session_id in self.conversation_context:
            context = self.conversation_context[session_id]
            if context.get('step') == 'application_confirmed':
                return context.get('application_data')
        return None
    
    def clear_session(self, session_id):
        """Очистка сессии."""
        if session_id in self.conversation_context:
            del self.conversation_context[session_id]
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]
