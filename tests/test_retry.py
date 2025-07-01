import asyncio
import types
import httpx
import logging
import pytest

from bot import whatsapp, ai_client

class DummySettings:
    WHATSAPP_PHONE_NUMBER_ID = "id"
    WHATSAPP_ACCESS_TOKEN = "token"

@pytest.mark.asyncio
async def test_send_message_retries(monkeypatch, caplog):
    attempts = 0

    async def fake_post(url, json=None, headers=None):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError('fail', request=httpx.Request('POST', url))
        return httpx.Response(200, request=httpx.Request('POST', url))

    monkeypatch.setattr(whatsapp, "_client", types.SimpleNamespace(post=fake_post))
    monkeypatch.setattr(whatsapp, "get_settings", lambda: DummySettings())
    caplog.set_level(logging.ERROR)
    await whatsapp.send_message('123', 'hi', retries=3, backoff=0)
    assert attempts == 3
    assert sum('attempt 1 failed' in r.getMessage() for r in caplog.records) == 1
    assert sum('attempt 2 failed' in r.getMessage() for r in caplog.records) == 1

@pytest.mark.asyncio
async def test_create_chat_completion_retries(monkeypatch, caplog):
    attempts = 0

    async def fake_create(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception('temp')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='ok'))])

    fake_client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=fake_create)))
    monkeypatch.setattr(ai_client, 'get_openai_client', lambda: fake_client)
    monkeypatch.setattr(ai_client, 'get_settings', lambda: DummySettings())

    caplog.set_level(logging.ERROR)
    resp = await ai_client.create_chat_completion(model='gpt', messages=[] , retries=3, backoff=0)
    assert attempts == 3
    assert resp.choices[0].message.content == 'ok'
    assert sum('attempt 1 failed' in r.getMessage() for r in caplog.records) == 1
    assert sum('attempt 2 failed' in r.getMessage() for r in caplog.records) == 1
