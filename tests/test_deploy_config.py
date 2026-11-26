import deploy.setup_sprites as setup


def test_deny_all_policy_is_explicit_wildcard_deny():
    assert setup.deny_all_policy() == {"rules": [{"domain": "*", "action": "deny"}]}


def test_webhook_payload_uses_secret_header_contract():
    payload = setup.webhook_payload("https://butler.example/", "secret")
    assert payload["url"] == "https://butler.example/api/webhooks/telegram"
    assert payload["secret_token"] == "secret"
    assert "callback_query" in payload["allowed_updates"]


def test_probe_covers_connector_paths_without_printing_secrets(monkeypatch):
    monkeypatch.setenv("SPRITES_API_TOKEN", "fly-secret")
    monkeypatch.setenv("TELEGRAM_CONNECTION_ID", "telegram-secret")
    result = setup.probe(dry_run=True)
    text = str(result)
    assert "airlock_self_proxy" in result and "pinecone" in result
    assert "telegram-secret" not in text and "fly-secret" not in text
    assert result["pinecone"]["requires_precreated_index"] is True
