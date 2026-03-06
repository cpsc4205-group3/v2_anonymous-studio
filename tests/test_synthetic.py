from __future__ import annotations

from services.synthetic import SyntheticConfig, synthesize_from_anonymized_text


def test_synthesize_returns_input_when_no_placeholders():
    cfg = SyntheticConfig(provider="faker")
    text = "No placeholders here."
    res = synthesize_from_anonymized_text(text, cfg)
    assert res.text == text
    assert res.backend == "none"


def test_synthesize_with_faker_replaces_common_placeholders():
    cfg = SyntheticConfig(provider="faker")
    src = "Patient <PERSON> from <LOCATION> called <PHONE_NUMBER>."
    res = synthesize_from_anonymized_text(src, cfg)
    assert "<PERSON>" not in res.text
    assert "<LOCATION>" not in res.text
    assert "<PHONE_NUMBER>" not in res.text
    assert res.backend == "faker"


def test_synthesize_openai_without_key_falls_back_to_faker():
    cfg = SyntheticConfig(provider="openai", api_key="")
    src = "Email: <EMAIL_ADDRESS>"
    res = synthesize_from_anonymized_text(src, cfg)
    assert "<EMAIL_ADDRESS>" not in res.text
    assert res.backend == "faker"
    assert "No API key" in res.message
