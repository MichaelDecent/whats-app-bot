# WhatsApp Bot

This FastAPI project implements a simple WhatsApp bot with support for placing food orders and chatting with an AI nutritionist. Messages are delivered using the WhatsApp Cloud API.

## Background sending

Sending WhatsApp messages may take a few seconds. Endpoints in `app.py` now schedule message delivery using FastAPI `BackgroundTasks`. Messages are placed on an internal queue and processed asynchronously so the webhook can respond immediately without waiting for the API call to finish.

## Running

Install dependencies and run the server:

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

