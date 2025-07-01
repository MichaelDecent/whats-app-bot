# WhatsApp Bot

This project is a small WhatsApp bot powered by FastAPI and MongoDB.

## Setup

1. Install the Python dependencies:

```bash
pip install -r requirements.txt
```

2. Copy the example environment file and fill in the values:

```bash
cp .env.example .env
```

`SESSION_TTL_SECONDS` controls how long a user session is stored. The default
in the example is **10800** (3 hours). MongoDB automatically purges expired
sessions thanks to the TTL index defined in `bot/database.py`.

3. Start the application:

```bash
uvicorn app:app
```

