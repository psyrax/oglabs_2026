import os
import sys
import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "scripts"))

from llm_client import get_client, OllamaClient, ClaudeClient, OpenAIClient, LLMClient


def test_get_client_ollama():
    client = get_client("ollama")
    assert isinstance(client, OllamaClient)


def test_get_client_claude():
    client = get_client("claude")
    assert isinstance(client, ClaudeClient)


def test_get_client_openai():
    client = get_client("openai")
    assert isinstance(client, OpenAIClient)


def test_get_client_uses_env_var(monkeypatch):
    monkeypatch.setenv("OGLABS_LLM", "ollama")
    client = get_client(None)
    assert isinstance(client, OllamaClient)


def test_get_client_invalid_backend():
    with pytest.raises(ValueError, match="Unknown LLM backend"):
        get_client("unknown")


def test_ollama_complete_calls_api(requests_mock):
    requests_mock.post(
        "http://localhost:11434/api/generate",
        json={"response": "Una foto hermosa."},
    )
    client = OllamaClient()
    result = client.complete("Describe esta foto.")
    assert result == "Una foto hermosa."


def test_ollama_complete_with_image(tmp_path, requests_mock):
    img = tmp_path / "test.jpg"
    img.write_bytes(b"fake-image-data")
    requests_mock.post(
        "http://localhost:11434/api/generate",
        json={"response": "Descripción de imagen."},
    )
    client = OllamaClient()
    result = client.complete("Describe.", image_path=str(img))
    assert result == "Descripción de imagen."
    # Verify image was sent as base64
    sent = requests_mock.last_request.json()
    assert "images" in sent


def test_claude_complete_calls_sdk(mocker):
    mock_anthropic = mocker.patch("llm_client.anthropic")
    mock_client = mock_anthropic.Anthropic.return_value
    mock_client.messages.create.return_value = mocker.Mock(
        content=[mocker.Mock(text="Texto mejorado.")]
    )
    client = ClaudeClient()
    result = client.complete("Mejora esto.")
    assert result == "Texto mejorado."
    mock_client.messages.create.assert_called_once()


def test_openai_complete_calls_sdk(mocker):
    mock_openai_module = mocker.patch("llm_client.OpenAI")
    mock_instance = mock_openai_module.return_value
    mock_instance.chat.completions.create.return_value = mocker.Mock(
        choices=[mocker.Mock(message=mocker.Mock(content="Respuesta."))]
    )
    client = OpenAIClient()
    result = client.complete("Hola.")
    assert result == "Respuesta."
