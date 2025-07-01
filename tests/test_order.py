import types
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bot.services import order

class DummyCollection:
    def __init__(self):
        self.deleted = None
        self.updated = None
    async def delete_one(self, query):
        self.deleted = query
    async def update_one(self, query, update):
        self.updated = (query, update)

class DummyDB:
    def __init__(self):
        self.sessions = DummyCollection()

def setup_env(monkeypatch):
    db = DummyDB()
    monkeypatch.setattr(order, "get_db", lambda: db)
    monkeypatch.setattr(order, "get_settings", lambda: types.SimpleNamespace(DELIVERY_PHONE_NUMBER=None))
    sent = []
    async def fake_send(uid, text):
        sent.append((uid, text))
    monkeypatch.setattr(order, "send_message", fake_send)
    return db, sent

@pytest.mark.asyncio
async def test_cancel_flow(monkeypatch):
    db, sent = setup_env(monkeypatch)
    session = {"step": "await_items", "data": {}}
    result = await order.handle("u1", "cancel", session)
    assert result["status"] == "cancelled"
    assert db.sessions.deleted == {"user_id": "u1"}
    assert "cancel" in sent[-1][1].lower()

@pytest.mark.asyncio
async def test_edit_flow(monkeypatch):
    db, sent = setup_env(monkeypatch)
    session = {"step": "await_confirm", "data": {}}
    result = await order.handle("u2", "edit", session)
    assert result["status"] == "awaiting"
    assert db.sessions.updated[0] == {"user_id": "u2"}
    assert db.sessions.updated[1]["$set"]["step"] == "await_items"
    assert "retype" in sent[-1][1].lower()
