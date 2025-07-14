# Развертывание AI Nutrition Bot

Этот документ описывает как развернуть бота в Docker и Docker Swarm.

## 📋 Требования

- Docker 20.10+
- Docker Compose 3.8+
- Docker Swarm (для продакшн развертывания)
- 2GB RAM минимум
- 10GB свободного места

## 🔧 Подготовка

### 1. Создание .env файла

Скопируйте переменные окружения:

```bash
cp .env.example .env
```

Заполните обязательные переменные:

```env
# Bot Configuration
BOT_TOKEN=your_telegram_bot_token_here
DEBUG=false
LOG_LEVEL=INFO

# Database Configuration
DATABASE_URL=postgresql://nutrition_user:nutrition_pass@db:5432/nutrition_bot
DATABASE_ECHO=false

# PostgreSQL Settings (for Docker)
POSTGRES_DB=nutrition_bot
POSTGRES_USER=nutrition_user
POSTGRES_PASSWORD=your_secure_postgres_password

# Redis Configuration
REDIS_URL=redis://:redis_pass@redis:6379/0
REDIS_PASSWORD=your_secure_redis_password

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o

# Nutrition Analysis Settings
MAX_PHOTO_SIZE=20971520
```

### 2. Сборка Docker образа

```bash
# Сборка образа
docker build -t nutrition-bot:latest .

# Или с тегом версии
docker build -t nutrition-bot:v1.0.0 .
```

## 🐳 Локальное развертывание (Docker Compose)

### Запуск

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down
```

### Управление базой данных

```bash
# Применение миграций
docker-compose exec bot uv run alembic upgrade head

# Создание новой миграции
docker-compose exec bot uv run alembic revision --autogenerate -m "description"

# Подключение к PostgreSQL
docker-compose exec db psql -U nutrition_user -d nutrition_bot
```

## 🚀 Продакшн развертывание (Docker Swarm)

### 1. Инициализация Swarm

```bash
# На manager ноде
docker swarm init

# Добавление worker нод (выполнить на worker машинах)
docker swarm join --token <token> <manager-ip>:2377
```

### 2. Создание секретов

```bash
# Создание секретов для чувствительных данных
echo "your_postgres_password" | docker secret create postgres_password -
echo "your_redis_password" | docker secret create redis_password -
echo "your_bot_token" | docker secret create bot_token -
echo "your_openai_api_key" | docker secret create openai_api_key -
```

### 3. Развертывание стека

```bash
# Развертывание
docker stack deploy -c docker-swarm.yml nutrition-bot

# Проверка статуса
docker service ls
docker stack ps nutrition-bot

# Просмотр логов
docker service logs nutrition-bot_bot -f
```

### 4. Масштабирование

```bash
# Увеличение количества реплик бота
docker service scale nutrition-bot_bot=3

# Обновление сервиса
docker service update --image nutrition-bot:v1.1.0 nutrition-bot_bot
```

### 5. Мониторинг

```bash
# Статус сервисов
docker service ls

# Детали конкретного сервиса
docker service ps nutrition-bot_bot

# Логи сервиса
docker service logs nutrition-bot_bot

# Использование ресурсов
docker stats $(docker ps --format "table {{.Names}}" | grep nutrition-bot)
```

## 🛠 Обслуживание

### Обновление

```bash
# 1. Сборка нового образа
docker build -t nutrition-bot:v1.1.0 .

# 2. Обновление в Swarm
docker service update --image nutrition-bot:v1.1.0 nutrition-bot_bot

# 3. Применение миграций (если нужно)
docker run --rm --network nutrition-bot_nutribot-network \
  --env-file .env nutrition-bot:v1.1.0 \
  uv run alembic upgrade head
```

### Резервное копирование

```bash
# Создание бэкапа базы данных
docker exec $(docker ps -q -f name=nutrition-bot_db) \
  pg_dump -U nutrition_user nutrition_bot > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановление из бэкапа
docker exec -i $(docker ps -q -f name=nutrition-bot_db) \
  psql -U nutrition_user -d nutrition_bot < backup.sql
```

### Очистка

```bash
# Удаление стека
docker stack rm nutrition-bot

# Очистка неиспользуемых ресурсов
docker system prune -a

# Удаление volumes (ОСТОРОЖНО!)
docker volume rm nutrition-bot_postgres_data nutrition-bot_redis_data
```

## 🔍 Отладка

### Общие проблемы

1. **Бот не отвечает**
   ```bash
   # Проверка логов
   docker service logs nutrition-bot_bot
   
   # Проверка health check
   docker service ps nutrition-bot_bot
   ```

2. **Ошибки подключения к базе данных**
   ```bash
   # Проверка статуса PostgreSQL
   docker service ps nutrition-bot_db
   
   # Тест подключения
   docker exec -it $(docker ps -q -f name=nutrition-bot_db) \
     psql -U nutrition_user -d nutrition_bot -c "SELECT 1;"
   ```

3. **Проблемы с Redis**
   ```bash
   # Проверка Redis
   docker exec -it $(docker ps -q -f name=nutrition-bot_redis) \
     redis-cli -a your_redis_password ping
   ```

### Полезные команды

```bash
# Подключение к контейнеру бота
docker exec -it $(docker ps -q -f name=nutrition-bot_bot) /bin/bash

# Просмотр конфигурации Swarm
docker node ls
docker network ls
docker service ls

# Мониторинг ресурсов
docker stats --no-stream
```

## ⚙️ Переменные окружения

| Переменная | Описание | Обязательная | По умолчанию |
|------------|----------|--------------|--------------|
| BOT_TOKEN | Токен Telegram бота | ✅ | - |
| DATABASE_URL | URL PostgreSQL | ✅ | - |
| OPENAI_API_KEY | API ключ OpenAI | ✅ | - |
| REDIS_URL | URL Redis | ❌ | redis://localhost:6379/0 |
| DEBUG | Режим отладки | ❌ | false |
| LOG_LEVEL | Уровень логирования | ❌ | INFO |
| OPENAI_MODEL | Модель OpenAI | ❌ | gpt-4o |

## 📊 Мониторинг производительности

Рекомендуется настроить мониторинг:

- **Prometheus + Grafana** для метрик
- **ELK Stack** для логов
- **Alertmanager** для уведомлений

Основные метрики для мониторинга:
- Использование CPU и RAM
- Количество активных пользователей
- Время ответа OpenAI API
- Статус подключений к БД и Redis 