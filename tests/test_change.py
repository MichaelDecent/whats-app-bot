import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bot.services import order


class DummySettings:
    DELIVERY_PHONE_NUMBER = None


class DummySessionUtils:
    def __init__(self):
        self.updated_sessions = []

    async def update(self, user_id, **fields):
        self.updated_sessions.append((user_id, fields))


class DummySession:
    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_change_moves_to_await_items(monkeypatch):
    session_mock = DummySessionUtils()
    dummy_db_session = DummySession()

    monkeypatch.setattr(order, "session_utils", session_mock)
    monkeypatch.setattr(order, "get_db", lambda: dummy_db_session)
    monkeypatch.setattr(order, "get_settings", lambda: DummySettings())
    messages = []

    async def fake_send_message(uid, txt):
        messages.append(txt)

    monkeypatch.setattr(order, "send_message", fake_send_message)

    session = {"step": "await_confirm", "data": {}}
    res = await order.handle("u", "change", session)
    assert res["status"] == "awaiting"
    assert len(session_mock.updated_sessions) > 0
    user_id, fields = session_mock.updated_sessions[-1]
    assert user_id == "u"
    assert fields.get("step") == "await_items"
