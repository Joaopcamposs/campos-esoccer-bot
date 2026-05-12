"""Testes do cliente Telegram."""

from unittest.mock import MagicMock

from telegram import client


async def test_send_message(mock_telegram):
    """Verifica envio de mensagem com parse_mode HTML padrão."""
    result = await client.send_message(123, "hello")
    assert result["ok"] is True
    assert result["result"]["message_id"] == 42
    mock_telegram.post.assert_called_once()
    call_kwargs = mock_telegram.post.call_args[1]["json"]
    assert call_kwargs["parse_mode"] == "HTML"


async def test_edit_message_text(mock_telegram):
    """Verifica edição de mensagem."""
    result = await client.edit_message_text(123, 42, "edited")
    assert result["ok"] is True
    mock_telegram.post.assert_called_once()


async def test_send_photo(mock_telegram):
    """Verifica envio de foto."""
    result = await client.send_photo(123, "https://example.com/photo.jpg", "caption")
    assert result["ok"] is True
    mock_telegram.post.assert_called_once()


async def test_edit_message_media(mock_telegram):
    """Verifica edição de mídia."""
    media = {"type": "photo", "media": "https://example.com/new.jpg"}
    result = await client.edit_message_media(123, 42, media)
    assert result["ok"] is True


async def test_api_call(mock_telegram):
    """Verifica chamada genérica à API."""
    result = await client.api_call("getMe")
    assert result["ok"] is True


async def test_retry_on_429(mock_telegram):
    """Verifica retry quando Telegram retorna 429."""
    rate_limit_resp = MagicMock()
    rate_limit_resp.status_code = 429
    rate_limit_resp.json.return_value = {"parameters": {"retry_after": 0}}

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.json.return_value = {"ok": True, "result": {"message_id": 42}}
    ok_resp.raise_for_status = MagicMock()

    mock_telegram.post.side_effect = [rate_limit_resp, ok_resp]
    result = await client.api_call("sendMessage", chat_id=123, text="test")
    assert result["ok"] is True
    assert mock_telegram.post.call_count == 2
