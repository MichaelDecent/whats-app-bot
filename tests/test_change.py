import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bot.services import order


class DummySettings:
    DELIVERY_PHONE_NUMBER = None

class DummyCollection:
    def __init__(self):
        self.updated = []
    async def update_one(self, filt, update):
        self.updated.append(update)

class DummyDB:
    def __init__(self):
        self.sessions = DummyCollection()

def fake_get_db():
    return DummyDB()

@pytest.mark.asyncio
async def test_change_moves_to_await_items(monkeypatch):
    db = DummyDB()
    monkeypatch.setattr(order, "get_db", lambda: db)
    monkeypatch.setattr(order, "get_settings", lambda: DummySettings())
    messages = []
    async def fake_send_message(uid, txt):
        messages.append(txt)
    monkeypatch.setattr(order, "send_message", fake_send_message)

    session = {"step": "await_confirm", "data": {}}
    res = await order.handle("u", "change", session)
    assert res["status"] == "awaiting"
    assert db.sessions.updated
    assert db.sessions.updated[-1]["$set"]["step"] == "await_items"

