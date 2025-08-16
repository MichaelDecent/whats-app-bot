import types
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bot.services import order
from bot import session as session_utils


class DummySessionUtils:
    def __init__(self):
        self.deleted_users = []
        self.updated_sessions = []

    async def delete(self, user_id):
        self.deleted_users.append(user_id)

    async def update(self, user_id, **fields):
        self.updated_sessions.append((user_id, fields))


class DummySession:
    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def setup_env(monkeypatch):
    session_mock = DummySessionUtils()
    dummy_db_session = DummySession()

    monkeypatch.setattr(order, "session_utils", session_mock)
    monkeypatch.setattr(order, "get_db", lambda: dummy_db_session)
    monkeypatch.setattr(
        order, "get_settings", lambda: types.SimpleNamespace(DELIVERY_PHONE_NUMBER=None)
    )
    sent = []

    async def fake_send(uid, text):
        sent.append((uid, text))

    monkeypatch.setattr(order, "send_message", fake_send)
    return session_mock, sent


@pytest.mark.asyncio
async def test_cancel_flow(monkeypatch):
    session_mock, sent = setup_env(monkeypatch)
    session = {"step": "await_items", "data": {}}
    result = await order.handle("u1", "cancel", session)
    assert result["status"] == "cancelled"
    assert "u1" in session_mock.deleted_users
    assert "cancel" in sent[-1][1].lower()


@pytest.mark.asyncio
async def test_edit_flow(monkeypatch):
    session_mock, sent = setup_env(monkeypatch)
    session = {"step": "await_confirm", "data": {}}
    result = await order.handle("u2", "edit", session)
    assert result["status"] == "awaiting"
    # Check that update was called with correct parameters
    assert len(session_mock.updated_sessions) > 0
    user_id, fields = session_mock.updated_sessions[-1]
    assert user_id == "u2"
    assert fields.get("step") == "await_items"
    assert "retype" in sent[-1][1].lower()
