#!/usr/bin/env python3
"""
Database utilities for the Nutrition Bot.
Convenient wrapper around Alembic commands.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(e.stderr)
        return False


def init_database():
    """Initialize database with migrations"""
    print("🚀 Initializing database with Alembic...")
    
    # Check if .env exists
    if not Path(".env").exists():
        print("⚠️  .env file not found. Please create it with DATABASE_URL")
        print("Example: DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname")
        return False
    
    # Apply migrations
    if not run_command(["uv", "run", "alembic", "upgrade", "head"], "Applying migrations"):
        return False
    
    print("🎉 Database initialization completed!")
    return True


def create_migration(message: str = None):
    """Create a new migration"""
    if not message:
        message = input("Enter migration description: ")
    
    return run_command(
        ["uv", "run", "alembic", "revision", "--autogenerate", "-m", message],
        f"Creating migration: {message}"
    )


def show_status():
    """Show current migration status"""
    print("📊 Database migration status:")
    
    # Show current version
    run_command(["uv", "run", "alembic", "current"], "Current version")
    
    # Show migration history
    run_command(["uv", "run", "alembic", "history"], "Migration history")


def rollback():
    """Rollback one migration"""
    if input("⚠️  Are you sure you want to rollback? (y/N): ").lower() != 'y':
        print("Rollback cancelled")
        return
    
    run_command(["uv", "run", "alembic", "downgrade", "-1"], "Rolling back migration")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("🛠️  Database Utilities for Nutrition Bot")
        print("\nUsage:")
        print("  uv run python db_utils.py init           - Initialize database")
        print("  uv run python db_utils.py migrate [msg]  - Create new migration")
        print("  uv run python db_utils.py status         - Show migration status")
        print("  uv run python db_utils.py rollback       - Rollback last migration")
        return
    
    command = sys.argv[1]
    
    if command == "init":
        init_database()
    elif command == "migrate":
        message = sys.argv[2] if len(sys.argv) > 2 else None
        create_migration(message)
    elif command == "status":
        show_status()
    elif command == "rollback":
        rollback()
    else:
        print(f"❌ Unknown command: {command}")


if __name__ == "__main__":
    main() 