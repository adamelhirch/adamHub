import json

from app.api import video as video_api
from app.services import video_intake


def test_extract_video_source_youtube_caption_and_metadata(monkeypatch):
    player_response = {
        "videoDetails": {
            "title": "Pasta night",
            "shortDescription": "Make pasta with pantry staples",
            "author": "Chef Ada",
            "thumbnail": {"thumbnails": [{"url": "https://img.test/thumb.jpg"}]},
        },
        "captions": {
            "playerCaptionsTracklistRenderer": {
                "captionTracks": [
                    {
                        "baseUrl": "https://example.test/captions",
                    }
                ]
            }
        },
    }
    html = f"""
    <html>
      <head>
        <meta property="og:title" content="Fallback title" />
        <meta name="description" content="Fallback description" />
      </head>
      <body>
        <script>var ytInitialPlayerResponse = {json.dumps(player_response)};</script>
      </body>
    </html>
    """

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self):
            self.requests = []

        def get(self, url):
            self.requests.append(url)
            assert url.startswith("https://example.test/captions")
            return FakeResponse(
                {
                    "events": [
                        {"tStartMs": 0, "dDurationMs": 1200, "segs": [{"utf8": "Boil "}, {"utf8": "water"}]},
                        {"tStartMs": 1500, "dDurationMs": 1200, "segs": [{"utf8": "Add pasta"}]},
                    ]
                }
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(video_intake, "_fetch_html", lambda url: (html, url))
    monkeypatch.setattr(video_intake, "_http_client", lambda: FakeClient())

    result = video_intake.extract_video_source("https://www.youtube.com/watch?v=abc123")

    assert result.platform == "youtube"
    assert result.title == "Pasta night"
    assert result.description == "Make pasta with pantry staples"
    assert result.author == "Chef Ada"
    assert result.transcript == "Boil water Add pasta"
    assert len(result.transcript_segments) == 2


def test_extract_video_source_youtube_uses_whisper_fallback(monkeypatch):
    html = """
    <html>
      <head>
        <meta property="og:title" content="Fallback title" />
        <meta name="description" content="Fallback description" />
      </head>
      <body>
        <script>var ytInitialPlayerResponse = {"videoDetails":{"title":"Fallback title","shortDescription":"Fallback description"}};</script>
      </body>
    </html>
    """

    class FakeSegment:
        def __init__(self, start, end, text):
            self.start = start
            self.end = end
            self.text = text

    class FakeModel:
        def transcribe(self, audio_path, beam_size=1, vad_filter=True):  # noqa: ARG002
            return iter([FakeSegment(0.0, 1.0, "Mix the sauce"), FakeSegment(1.1, 2.0, "Serve hot")]), None

    monkeypatch.setattr(video_intake, "_fetch_html", lambda url: (html, url))
    monkeypatch.setattr(video_intake, "_download_audio_file", lambda url: ("/tmp/audio.mp3", "sample", "/tmp/whisper-test"))  # noqa: ARG005
    monkeypatch.setattr(video_intake, "_load_whisper_model", lambda model_size, device, compute_type: FakeModel())  # noqa: ARG005

    result = video_intake.extract_video_source("https://www.youtube.com/watch?v=abc123")

    assert result.platform == "youtube"
    assert result.transcript == "Mix the sauce Serve hot"
    assert result.transcript_source == "whisper_local:base"
    assert len(result.transcript_segments) == 2




def test_video_extract_endpoint_returns_payload(monkeypatch, client, auth_headers):
    def fake_extract(url: str):
        return video_intake.VideoSourceRead(
            url=url,
            canonical_url=url,
            platform="youtube",
            title="Sample",
            description="Desc",
            transcript="Line 1",
            transcript_source="caption",
            transcript_segments=[],
            warnings=[],
        )

    monkeypatch.setattr(video_api, "extract_video_source", fake_extract)

    response = client.post(
        "/api/v1/video/extract",
        headers=auth_headers,
        json={"url": "https://www.youtube.com/watch?v=abc123"},
    )

    assert response.status_code == 200
    assert response.json()["platform"] == "youtube"
    assert response.json()["transcript"] == "Line 1"
