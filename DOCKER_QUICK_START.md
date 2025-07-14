# 🚀 Quick Start Guide - Docker Deployment

Быстрый старт для развертывания AI Nutrition Bot в Docker.

## ⚡ Локальная разработка

### 1. Подготовка

```bash
# Клонирование репозитория
git clone <repository-url>
cd ai_nutritiolog_bot

# Создание файла конфигурации
cp env.example .env
```

### 2. Настройка .env

Отредактируйте `.env` файл:

```env
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
OPENAI_API_KEY=YOUR_OPENAI_KEY_HERE
POSTGRES_PASSWORD=secure_password_123
REDIS_PASSWORD=secure_redis_pass
```

### 3. Запуск

```bash
# Запуск через deployment script
./deploy.sh dev:start

# Или напрямую через docker-compose
docker-compose up -d
```

### 4. Проверка

```bash
# Логи бота
./deploy.sh dev:logs

# Статус контейнеров
docker-compose ps
```

---

## 🏭 Продакшн развертывание

### 1. Инициализация Swarm

```bash
# Инициализация Docker Swarm
./deploy.sh prod:init

# Или вручную
docker swarm init
```

### 2. Развертывание

```bash
# Развертывание стека
./deploy.sh prod:deploy

# Проверка статуса
./deploy.sh prod:status
```

### 3. Масштабирование

```bash
# Увеличение до 3 реплик
./deploy.sh prod:scale 3

# Просмотр логов
./deploy.sh prod:logs
```

---

## 🛠 Основные команды

### Разработка
```bash
./deploy.sh dev:start    # Запуск разработки
./deploy.sh dev:stop     # Остановка
./deploy.sh dev:logs     # Логи
./deploy.sh dev:shell    # Доступ к контейнеру
```

### Продакшн
```bash
./deploy.sh prod:deploy  # Развертывание
./deploy.sh prod:update  # Обновление
./deploy.sh prod:scale 2 # Масштабирование
./deploy.sh prod:status  # Статус
```

### База данных
```bash
./deploy.sh db:migrate   # Миграции
./deploy.sh db:backup    # Резервное копирование
```

---

## 📊 Мониторинг

### Проверка здоровья

```bash
# Docker Compose
docker-compose ps
docker-compose logs bot

# Docker Swarm
docker service ls
docker service ps nutrition-bot_bot
docker service logs nutrition-bot_bot
```

### Использование ресурсов

```bash
# Статистика контейнеров
docker stats

# Использование volumes
docker volume ls
docker system df
```

---

## 🔧 Troubleshooting

### Частые проблемы

**1. Бот не запускается**
```bash
# Проверка логов
./deploy.sh dev:logs

# Проверка переменных окружения
docker-compose exec bot env | grep BOT_TOKEN
```

**2. База данных недоступна**
```bash
# Проверка PostgreSQL
docker-compose exec db pg_isready -U nutrition_user

# Подключение к БД
docker-compose exec db psql -U nutrition_user -d nutrition_bot
```

**3. Проблемы с Redis**
```bash
# Проверка Redis
docker-compose exec redis redis-cli -a your_password ping
```

### Очистка

```bash
# Остановка и очистка
./deploy.sh dev:stop
./deploy.sh cleanup

# Полная очистка (ОСТОРОЖНО!)
docker-compose down -v
docker system prune -a
```

---

## 📁 Структура файлов

```
ai_nutritiolog_bot/
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Локальная разработка  
├── docker-swarm.yml        # Продакшн Swarm
├── deploy.sh               # Скрипт развертывания
├── .dockerignore           # Исключения для Docker
├── env.example             # Пример переменных
├── DEPLOYMENT.md           # Полная документация
└── DOCKER_QUICK_START.md   # Этот файл
```

---

## 🎯 Следующие шаги

1. **Настройка мониторинга**: Prometheus + Grafana
2. **Настройка CI/CD**: GitHub Actions или GitLab CI
3. **Резервное копирование**: Автоматические бэкапы БД
4. **Балансировка нагрузки**: NGINX или Traefik
5. **Логирование**: ELK Stack или Loki

---

## 💡 Полезные ссылки

- [DEPLOYMENT.md](DEPLOYMENT.md) - Подробная документация
- [Docker Compose docs](https://docs.docker.com/compose/)
- [Docker Swarm docs](https://docs.docker.com/engine/swarm/)
- [uv Package Manager](https://github.com/astral-sh/uv) 