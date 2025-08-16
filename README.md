# WhatsApp Bot

This project is a small WhatsApp bot powered by FastAPI and SQL databases (SQLite for development, PostgreSQL for production).

## Database Support

- **Development**: SQLite (default) - No additional setup required
- **Production**: PostgreSQL - Set `DATABASE_URL` environment variable

## Setup

1. Install the Python dependencies:

```bash
pip install -r requirements.txt
```

2. Copy the example environment file and fill in the values:

```bash
cp .env.example .env
```

### Environment Variables

- `DATABASE_URL`: Database connection string (defaults to SQLite: `sqlite+aiosqlite:///./whatsapp_bot.db`)
  - For PostgreSQL: `postgresql+asyncpg://username:password@host:port/database`
  - For SQLite (dev): `sqlite+aiosqlite:///./whatsapp_bot.db`
- `SESSION_TTL_SECONDS`: How long user sessions are stored (default: 3600 seconds = 1 hour)
- Other WhatsApp and AI configuration variables as needed

3. Initialize the database (optional, as it auto-initializes on startup):

```bash
python init_db.py
```

4. Start the application:

```bash
uvicorn app:app
```

## Database Migration

The application has been migrated from MongoDB to SQL databases:

- All data models are now SQLAlchemy-based
- Supports both SQLite (development) and PostgreSQL (production)
- Database tables are automatically created on startup
- No data migration script needed as this is a development phase change
