#!/bin/bash

# AI Nutrition Bot Deployment Script
# Usage: ./deploy.sh [command] [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="nutrition-bot"
IMAGE_NAME="nutrition-bot"
COMPOSE_FILE="docker-compose.yml"
SWARM_FILE="docker-swarm.yml"

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking requirements..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    if [ ! -f ".env" ]; then
        log_error ".env file not found. Please create it from .env.example"
        exit 1
    fi
    
    log_success "Requirements check passed"
}

build_image() {
    local version=${1:-latest}
    log_info "Building Docker image: ${IMAGE_NAME}:${version}"
    
    docker build -t "${IMAGE_NAME}:${version}" .
    
    log_success "Image built successfully"
}

# Development commands
dev_start() {
    log_info "Starting development environment..."
    check_requirements
    
    docker-compose up -d
    
    log_success "Development environment started"
    log_info "Bot logs: docker-compose logs -f bot"
}

dev_stop() {
    log_info "Stopping development environment..."
    
    docker-compose down
    
    log_success "Development environment stopped"
}

dev_logs() {
    docker-compose logs -f bot
}

dev_shell() {
    docker-compose exec bot /bin/bash
}

# Production commands
prod_init() {
    log_info "Initializing Docker Swarm..."
    
    if docker info --format '{{.Swarm.LocalNodeState}}' | grep -q "inactive"; then
        docker swarm init
        log_success "Docker Swarm initialized"
    else
        log_warning "Docker Swarm already initialized"
    fi
}

prod_deploy() {
    local version=${1:-latest}
    log_info "Deploying to production with image: ${IMAGE_NAME}:${version}"
    
    check_requirements
    
    # Build image if not exists
    if ! docker image inspect "${IMAGE_NAME}:${version}" &> /dev/null; then
        build_image "${version}"
    fi
    
    # Deploy stack
    docker stack deploy -c "${SWARM_FILE}" "${STACK_NAME}"
    
    log_success "Production deployment completed"
    log_info "Check status: docker service ls"
}

prod_update() {
    local version=${1:-latest}
    log_info "Updating production deployment to version: ${version}"
    
    build_image "${version}"
    
    # Update bot service
    docker service update --image "${IMAGE_NAME}:${version}" "${STACK_NAME}_bot"
    
    log_success "Production update completed"
}

prod_scale() {
    local replicas=${1:-2}
    log_info "Scaling bot service to ${replicas} replicas"
    
    docker service scale "${STACK_NAME}_bot=${replicas}"
    
    log_success "Scaling completed"
}

prod_logs() {
    docker service logs "${STACK_NAME}_bot" -f
}

prod_status() {
    log_info "Production stack status:"
    echo
    docker service ls
    echo
    docker stack ps "${STACK_NAME}"
}

prod_remove() {
    log_warning "This will remove the entire production stack!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker stack rm "${STACK_NAME}"
        log_success "Production stack removed"
    else
        log_info "Operation cancelled"
    fi
}

# Database commands
db_migrate() {
    log_info "Running database migrations..."
    
    if docker service ls | grep -q "${STACK_NAME}_bot"; then
        # Production environment
        docker run --rm --network "${STACK_NAME}_nutribot-network" \
            --env-file .env "${IMAGE_NAME}:latest" \
            uv run alembic upgrade head
    else
        # Development environment
        docker-compose exec bot uv run alembic upgrade head
    fi
    
    log_success "Database migrations completed"
}

db_backup() {
    local backup_file="backup_$(date +%Y%m%d_%H%M%S).sql"
    log_info "Creating database backup: ${backup_file}"
    
    if docker service ls | grep -q "${STACK_NAME}_db"; then
        # Production environment
        docker exec $(docker ps -q -f name="${STACK_NAME}_db") \
            pg_dump -U nutrition_user nutrition_bot > "${backup_file}"
    else
        # Development environment
        docker-compose exec -T db pg_dump -U nutrition_user nutrition_bot > "${backup_file}"
    fi
    
    log_success "Database backup created: ${backup_file}"
}

# Utility commands
cleanup() {
    log_info "Cleaning up Docker resources..."
    
    docker system prune -f
    docker volume prune -f
    
    log_success "Cleanup completed"
}

show_help() {
    cat << EOF
AI Nutrition Bot Deployment Script

Usage: $0 [COMMAND] [OPTIONS]

Development Commands:
  dev:start         Start development environment
  dev:stop          Stop development environment
  dev:logs          Show bot logs
  dev:shell         Access bot container shell

Production Commands:
  prod:init         Initialize Docker Swarm
  prod:deploy [ver] Deploy to production (default: latest)
  prod:update [ver] Update production deployment
  prod:scale [num]  Scale bot service (default: 2)
  prod:logs         Show production logs
  prod:status       Show production status
  prod:remove       Remove production stack

Database Commands:
  db:migrate        Run database migrations
  db:backup         Create database backup

Utility Commands:
  build [version]   Build Docker image
  cleanup           Clean up Docker resources
  help              Show this help

Examples:
  $0 dev:start                    # Start development
  $0 prod:deploy v1.0.0          # Deploy version 1.0.0
  $0 prod:scale 3                # Scale to 3 replicas
  $0 build v1.0.0                # Build specific version

EOF
}

# Main command handler
case "${1}" in
    "dev:start")
        dev_start
        ;;
    "dev:stop")
        dev_stop
        ;;
    "dev:logs")
        dev_logs
        ;;
    "dev:shell")
        dev_shell
        ;;
    "prod:init")
        prod_init
        ;;
    "prod:deploy")
        prod_deploy "${2}"
        ;;
    "prod:update")
        prod_update "${2}"
        ;;
    "prod:scale")
        prod_scale "${2}"
        ;;
    "prod:logs")
        prod_logs
        ;;
    "prod:status")
        prod_status
        ;;
    "prod:remove")
        prod_remove
        ;;
    "db:migrate")
        db_migrate
        ;;
    "db:backup")
        db_backup
        ;;
    "build")
        build_image "${2}"
        ;;
    "cleanup")
        cleanup
        ;;
    "help"|"--help"|"-h"|"")
        show_help
        ;;
    *)
        log_error "Unknown command: ${1}"
        echo
        show_help
        exit 1
        ;;
esac 