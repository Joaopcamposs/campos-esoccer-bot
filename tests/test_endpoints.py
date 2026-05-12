"""Testes dos endpoints HTTP."""


async def test_health(client):
    """Verifica health check."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


async def test_webhook_valid(client):
    """Verifica webhook com update válido."""
    update = {"message": {"chat": {"id": 123}, "text": "test"}}
    resp = await client.post("/webhook/telegram", json=update)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_webhook_no_message(client):
    """Verifica webhook com update sem message."""
    resp = await client.post("/webhook/telegram", json={"update_id": 1})
    assert resp.status_code == 200


async def test_send_endpoint(client):
    """Verifica endpoint de envio."""
    resp = await client.post(
        "/api/send", params={"text": "hello", "reference_key": "test-key"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message_id"] == 42
    assert data["reference_key"] == "test-key"
    assert data["status"] == "pending"


async def test_edit_endpoint_not_found(client):
    """Verifica 404 para edição de mensagem inexistente."""
    resp = await client.put("/api/edit", params={"reference_key": "nope", "text": "x"})
    assert resp.status_code == 404


async def test_edit_endpoint_success(client):
    """Verifica edição via endpoint após envio."""
    await client.post(
        "/api/send", params={"text": "original", "reference_key": "edit-me"}
    )
    resp = await client.put(
        "/api/edit", params={"reference_key": "edit-me", "text": "updated"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "edited"}


async def test_pending_endpoint(client):
    """Verifica listagem de pendentes via endpoint."""
    await client.post("/api/send", params={"text": "a", "reference_key": "p1"})
    await client.post("/api/send", params={"text": "b", "reference_key": "p2"})
    await client.put("/api/edit", params={"reference_key": "p1", "text": "done"})

    resp = await client.get("/api/pending")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["reference_key"] == "p2"


async def test_webhook_secret_validation(client):
    """Verifica que webhook funciona sem secret configurado."""
    update = {"message": {"chat": {"id": 123}, "text": "/ping"}}
    resp = await client.post("/webhook/telegram", json=update)
    assert resp.status_code == 200
