"""Testes do handler de webhook."""

from app.telegram.handler import handle_update


async def test_handle_start(mock_telegram):
    """Verifica comando /start."""
    update = {"message": {"chat": {"id": 123}, "text": "/start"}}
    await handle_update(update)
    mock_telegram.post.assert_called_once()


async def test_handle_ping(mock_telegram):
    """Verifica comando /ping."""
    update = {"message": {"chat": {"id": 123}, "text": "/ping"}}
    await handle_update(update)
    mock_telegram.post.assert_called_once()


async def test_handle_default_response(mock_telegram):
    """Verifica resposta padrão para mensagem qualquer."""
    update = {"message": {"chat": {"id": 123}, "text": "hello"}}
    await handle_update(update)
    mock_telegram.post.assert_called_once()


async def test_handle_no_message(mock_telegram):
    """Verifica que update sem message é ignorado."""
    await handle_update({"update_id": 1})
    mock_telegram.post.assert_not_called()
