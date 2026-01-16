# Настройка отправки email через SendGrid

## Преимущества SendGrid

- Надежная доставка писем
- Не требует пароля приложения
- Работает через SMTP Relay
- Бесплатный тариф: 100 писем в день

## Настройка

### 1. Создание аккаунта SendGrid

1. Зарегистрируйтесь на [sendgrid.com](https://sendgrid.com)
2. Подтвердите email
3. Создайте API ключ для SMTP

### 2. Создание API ключа

1. Войдите в панель SendGrid
2. Перейдите: **Settings** → **API Keys**
3. Нажмите **"Create API Key"**
4. Выберите права: **"Full Access"** или **"Mail Send"**
5. Скопируйте созданный API ключ (он показывается только один раз!)
   - Формат: `SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 3. Настройка отправителя (Sender)

1. Перейдите: **Settings** → **Sender Authentication**
2. Нажмите **"Verify a Single Sender"**
3. Заполните форму с вашим email адресом
4. Подтвердите email (проверьте почту)
5. После подтверждения email будет использоваться как отправитель

### 4. Настройка в проекте

Создайте/обновите файл `.env`:

```env
MAIL_PROVIDER=sendgrid
MAIL_PORT=587
MAIL_USERNAME=apikey
MAIL_PASSWORD=SG.ваш_api_ключ_от_sendgrid
MAIL_DEFAULT_SENDER=ваш_подтвержденный_email@example.com
```

**Важно:**
- `MAIL_USERNAME` всегда должен быть `apikey` (не ваш email!)
- `MAIL_PASSWORD` - это ваш API ключ SendGrid (начинается с `SG.`)
- `MAIL_DEFAULT_SENDER` - это email, который вы подтвердили в SendGrid

### 5. Альтернативные порты

**Порт 587 с TLS (рекомендуется):**
```env
MAIL_PROVIDER=sendgrid
MAIL_PORT=587
MAIL_USERNAME=apikey
MAIL_PASSWORD=SG.ваш_api_ключ
MAIL_DEFAULT_SENDER=ваш_email@example.com
```

**Порт 465 с SSL:**
```env
MAIL_PROVIDER=sendgrid
MAIL_PORT=465
MAIL_USERNAME=apikey
MAIL_PASSWORD=SG.ваш_api_ключ
MAIL_DEFAULT_SENDER=ваш_email@example.com
```

## Проверка работы

Запустите тестовый скрипт:
```bash
python test_sendgrid.py your_email@example.com
```

## Ограничения бесплатного тарифа

- 100 писем в день
- До 40,000 писем в месяц
- Один подтвержденный отправитель

## Решение проблем

### Письма не отправляются

1. **Проверьте API ключ:**
   - Убедитесь, что используете правильный API ключ
   - Проверьте, что ключ имеет права "Mail Send"

2. **Проверьте отправителя:**
   - Email в `MAIL_DEFAULT_SENDER` должен быть подтвержден в SendGrid
   - Проверьте папку "Спам" в SendGrid для письма подтверждения

3. **Проверьте логи:**
   - В панели SendGrid: **Activity** → **Email Activity**
   - Там будут видны все попытки отправки и ошибки

4. **Проверьте лимиты:**
   - Бесплатный тариф: 100 писем в день
   - Если превышен лимит, письма не будут отправляться

### Ошибка аутентификации

- Убедитесь, что `MAIL_USERNAME=apikey` (буквально слово "apikey")
- Проверьте, что API ключ правильный и не истек

### Письма попадают в спам

- Настройте SPF и DKIM записи в SendGrid
- Используйте подтвержденный домен вместо одного отправителя
