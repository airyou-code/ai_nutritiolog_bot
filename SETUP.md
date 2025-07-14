# 🚀 Быстрая настройка базы данных

## 📋 Инициализация базы данных SQLAlchemy + Alembic

### 1. Запустить PostgreSQL
```bash
# С Docker Compose (рекомендуется)
docker compose up -d db

# Или запустить PostgreSQL локально
```

### 2. Создать файл `.env`
```env
# Database Configuration
DATABASE_URL=postgresql+asyncpg://aichat:dev_password_123@localhost:5432/aichat_bot

# Bot Configuration
BOT_TOKEN=your_bot_token_here

# OpenAI Configuration  
OPENAI_API_KEY=your_openai_api_key_here

# Optional settings
REDIS_URL=redis://localhost:6379/0
DEBUG=false
LOG_LEVEL=INFO
```

### 3. Инициализировать базу данных
```bash
# Применить миграции (создать таблицы)
uv run alembic upgrade head

# Или через утилитный скрипт
uv run python db_utils.py init
```

### 4. Запустить бота
```bash
uv run python -m bot.main
```

## 🛠️ Команды управления базой данных

| Команда | Описание |
|---------|----------|
| `uv run python db_utils.py init` | Инициализация базы данных |
| `uv run python db_utils.py status` | Статус миграций |
| `uv run python db_utils.py migrate "описание"` | Создать новую миграцию |
| `uv run python db_utils.py rollback` | Откатить миграцию |

## 📊 Структура базы данных

**Созданные таблицы:**
- ✅ `telegram_users` - пользователи бота (ID, имя, настройки питания)
- ✅ `food_entries` - записи о еде (БЖУ, калории, фото, дата)
- ✅ `alembic_version` - версионирование схемы

## 🔧 Устранение проблем

**Ошибка "AttributeError: 'Message' object has no attribute 'message'"**
✅ **ИСПРАВЛЕНО** - middleware теперь правильно обрабатывает разные типы событий

**Ошибка "greenlet library is required"**
✅ **ИСПРАВЛЕНО** - добавлена зависимость `greenlet`

**Ошибка подключения к базе данных**
- Проверьте, что PostgreSQL запущен
- Убедитесь, что DATABASE_URL корректный в `.env`
- Проверьте пароль и имя базы данных 