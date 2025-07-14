# AI Nutrition Telegram Bot

Телеграм бот-нутрициолог с интеграцией OpenAI для анализа фотографий еды и подсчета БЖУ.

## Возможности

🔍 **Анализ еды по фото** - распознавание блюд и расчет БЖУ
📝 **Ввод текстом** - описание блюд с автоматическим анализом  
📊 **Дневник питания** - отслеживание ежедневного рациона
💬 **ИИ чат** - персональные советы по питанию
🎯 **Цели БЖУ** - установка и отслеживание целей

## Технологии

- **Python 3.12+** - основной язык
- **aiogram 3.19** - фреймворк для Telegram Bot API
- **OpenAI GPT-4o** - анализ изображений и генерация советов
- **PostgreSQL 16** - база данных
- **Redis** - кеширование и состояния
- **SQLAlchemy** - ORM для работы с БД
- **uv** - пакетный менеджер

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd ai_nutritiolog_bot
```

### 2. Установка зависимостей

Убедитесь, что у вас установлен [uv](https://github.com/astral-sh/uv):

```bash
# Установка uv (если не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Установка зависимостей
uv sync
```

### 3. Настройка базы данных

Установите PostgreSQL 16 и создайте базу данных:

```sql
CREATE DATABASE ai_nutritiolog_bot;
CREATE USER bot_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ai_nutritiolog_bot TO bot_user;
```

### 4. Настройка Redis (опционально)

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Запуск Redis
redis-server
```

### 5. Переменные окружения

Создайте файл `.env` в корне проекта:

```bash
# Bot Configuration
BOT_TOKEN=your_telegram_bot_token_here

# Database Configuration  
DATABASE_URL=postgresql+asyncpg://bot_user:your_password@localhost:5432/ai_nutritiolog_bot
DATABASE_ECHO=false

# Redis Configuration (optional)
REDIS_URL=redis://localhost:6379/0

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o

# Application Settings
DEBUG=false
LOG_LEVEL=INFO

# Photo upload limits
MAX_PHOTO_SIZE=20971520
```

### 6. Получение API ключей

#### Telegram Bot Token
1. Найдите [@BotFather](https://t.me/BotFather) в Telegram
2. Создайте бота командой `/newbot`
3. Скопируйте полученный токен

#### OpenAI API Key
1. Зарегистрируйтесь на [platform.openai.com](https://platform.openai.com)
2. Создайте API ключ в разделе API Keys
3. Убедитесь, что у вас есть доступ к GPT-4o

## Запуск

### Разработка

```bash
# Активация виртуального окружения
source .venv/bin/activate  # Linux/macOS
# или
.venv\Scripts\activate     # Windows

# Запуск бота
python -m bot.main
```

### Продакшн

```bash
# Запуск с uv
uv run python -m bot.main

# Или с использованием systemd/supervisor
```

## Структура проекта

```
ai_nutritiolog_bot/
├── bot/
│   ├── config/           # Настройки приложения
│   ├── database/         # Модели и операции БД
│   │   ├── models/       # SQLAlchemy модели
│   │   └── operations/   # Операции с БД
│   ├── handlers/         # Обработчики сообщений
│   ├── services/         # Сервисы (OpenAI, Redis)
│   ├── keyboards/        # Inline клавиатуры
│   ├── middlewares/      # Промежуточные обработчики
│   ├── utils/           # Вспомогательные функции
│   └── main.py          # Точка входа
├── pyproject.toml       # Конфигурация проекта
└── README.md           # Документация
```

## Использование

### Основные команды
- `/start` - запуск бота и показ главного меню
- `/menu` - показать главное меню
- `/help` - справка по использованию

### Функции

#### Анализ фото
1. Нажмите "📸 Сфотографировать еду"
2. Отправьте фото блюда
3. Выберите размер порции
4. Подтвердите добавление в дневник

#### Ввод текстом
1. Нажмите "✍️ Описать блюдо текстом"
2. Выберите простой или детальный ввод
3. Опишите блюдо
4. Выберите порцию и подтвердите

#### Дневник питания
- Просмотр записей за день
- Статистика за неделю
- Удаление записей

#### ИИ чат
- Задавайте вопросы о питании
- Получайте персональные советы
- Анализ вашего рациона

## Разработка

### Добавление новых функций

1. Создайте новый роутер в `bot/handlers/`
2. Добавьте необходимые клавиатуры в `bot/keyboards/`
3. Подключите роутер в `bot/main.py`

### Тестирование

```bash
# Запуск тестов
uv run pytest

# Линтинг
uv run black bot/
uv run isort bot/
```

## Деплой

### Docker (рекомендуется)

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install uv
RUN uv sync --frozen

CMD ["uv", "run", "python", "-m", "bot.main"]
```

### Systemd Service

```ini
[Unit]
Description=AI Nutrition Bot
After=network.target

[Service]
Type=simple
User=bot
WorkingDirectory=/path/to/ai_nutritiolog_bot
ExecStart=/path/to/.venv/bin/python -m bot.main
Restart=always

[Install]
WantedBy=multi-user.target
```

## Мониторинг

Бот логирует все важные события. Рекомендуется настроить сбор логов через:
- ELK Stack
- Grafana + Loki
- CloudWatch (AWS)

## Безопасность

- Храните API ключи в переменных окружения
- Используйте HTTPS для webhook (в продакшне)
- Ограничьте размер загружаемых фото
- Настройте rate limiting

## 🐳 Docker Развертывание

Бот поддерживает развертывание в Docker и Docker Swarm для продакшн использования.

### Быстрый старт

```bash
# Создание конфигурации
cp env.example .env
# Отредактируйте .env с вашими токенами

# Локальная разработка
./deploy.sh dev:start

# Продакшн развертывание
./deploy.sh prod:init     # Инициализация Swarm
./deploy.sh prod:deploy   # Развертывание
```

### Доступные файлы

- `Dockerfile` - Multi-stage сборка с uv
- `docker-compose.yml` - Локальная разработка
- `docker-swarm.yml` - Продакшн Swarm развертывание
- `deploy.sh` - Скрипт автоматизации развертывания
- `DEPLOYMENT.md` - Подробная документация
- `DOCKER_QUICK_START.md` - Руководство быстрого старта

### Особенности

- **Multi-stage build** с оптимизацией размера образа
- **Health checks** для всех сервисов
- **Auto-scaling** и zero-downtime обновления
- **Persistent storage** для PostgreSQL и Redis
- **Resource limits** и мониторинг
- **Automated migrations** и резервное копирование

## Лицензия

MIT License

## Поддержка

Для вопросов и предложений создавайте issues в репозитории.