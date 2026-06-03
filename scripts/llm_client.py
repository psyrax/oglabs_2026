import base64
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import anthropic
import requests


class LLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, image_path: Optional[str] = None) -> str:
        pass


class OllamaClient(LLMClient):
    def __init__(self, model: Optional[str] = None, host: Optional[str] = None):
        # Model and host are configurable so the same client can target a local
        # model (e.g. llava) or a cloud model on a remote host (e.g.
        # kimi-k2.6:cloud on the homelab Ollama).
        self.model = model or os.getenv("OLLAMA_MODEL", "llava")
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def complete(self, prompt: str, image_path: Optional[str] = None) -> str:
        payload: dict = {"model": self.model, "prompt": prompt, "stream": False}
        if image_path:
            with open(image_path, "rb") as f:
                payload["images"] = [base64.b64encode(f.read()).decode()]
        resp = requests.post(f"{self.host}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json()["response"]


class ClaudeClient(LLMClient):
    def __init__(self, model: str = "claude-opus-4-6"):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def complete(self, prompt: str, image_path: Optional[str] = None) -> str:
        content: list = []
        if image_path:
            with open(image_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": img_data},
            })
        content.append({"type": "text", "text": prompt})
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        return msg.content[0].text


def get_client(backend: Optional[str]) -> LLMClient:
    resolved = backend or os.getenv("OGLABS_LLM", "claude")
    if resolved == "ollama":
        return OllamaClient()
    if resolved == "claude":
        return ClaudeClient()
    raise ValueError(f"Unknown LLM backend: {resolved!r}. Choose ollama or claude.")
