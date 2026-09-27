import base64
from unittest.mock import patch
import pytest

from tests.conftest import register_user


def test_assistant_chat_with_images(client):
    user = register_user(client, "multimodal@example.com")

    payload = {
        "message": "Voici une photo de mon frigo",
        "images": ["data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP..."],
        "history": [],
    }

    res = client.post(
        "/api/v1/assistant/chat",
        headers=user["headers"],
        json=payload,
    )
    assert res.status_code == 200
    # SSE response
    assert "text/event-stream" in res.headers["content-type"]
    content = res.text
    assert "event: done" in content


def test_assistant_transcribe_audio(client, monkeypatch):
    user = register_user(client, "transcribe@example.com")

    class DummySegment:
        def __init__(self, text):
            self.text = text

    class DummyWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, path, language="fr"):
            return [DummySegment("Bonjour AdamHUB, prépare mon dîner")], None

    import faster_whisper
    monkeypatch.setattr(faster_whisper, "WhisperModel", DummyWhisperModel)

    dummy_audio_b64 = base64.b64encode(b"RIFFdummywavdata").decode("utf-8")
    payload = {
        "audio_base64": dummy_audio_b64,
        "mime_type": "audio/wav",
    }

    res = client.post(
        "/api/v1/assistant/transcribe",
        headers=user["headers"],
        json=payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert "text" in data
    assert "Bonjour AdamHUB" in data["text"]

