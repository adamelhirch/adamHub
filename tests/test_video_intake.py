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
    monkeypatch.setattr(video_intake, "_fetch_oembed", lambda url, platform: ({}, []))  # noqa: ARG005
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
    monkeypatch.setattr(video_intake, "_fetch_oembed", lambda url, platform: ({}, []))  # noqa: ARG005
    monkeypatch.setattr(video_intake, "_download_audio_file", lambda url: ("/tmp/audio.mp3", "sample", "/tmp/whisper-test"))  # noqa: ARG005
    monkeypatch.setattr(video_intake, "_load_whisper_model", lambda model_size, device, compute_type: FakeModel())  # noqa: ARG005

    result = video_intake.extract_video_source("https://www.youtube.com/watch?v=abc123")

    assert result.platform == "youtube"
    assert result.transcript == "Mix the sauce Serve hot"
    assert result.transcript_source == "whisper_local:base"
    assert len(result.transcript_segments) == 2


def test_extract_video_source_tiktok_prefers_structured_desc_over_generic_meta(monkeypatch):
    sigi_state = {
        "ItemModule": {
            "video-1": {
                "desc": "Pates creme citron en 10 minutes",
                "author": "chefada",
                "video": {
                    "subtitleInfos": [],
                },
            }
        }
    }
    html = f"""
    <html>
      <head>
        <meta property="og:title" content="TikTok" />
        <meta property="og:description" content="Watch more trending videos on TikTok" />
        <meta property="og:image" content="https://img.test/tiktok.jpg" />
      </head>
      <body>
        <script id="SIGI_STATE" type="application/json">{json.dumps(sigi_state)}</script>
      </body>
    </html>
    """

    monkeypatch.setattr(video_intake, "_fetch_html", lambda url: (html, url))
    monkeypatch.setattr(video_intake, "_fetch_oembed", lambda url, platform: ({}, []))  # noqa: ARG005
    monkeypatch.setattr(video_intake, "_whisper_transcribe", lambda url: (None, [], None, ["whisper_audio_download_failed"]))  # noqa: ARG005

    result = video_intake.extract_video_source("https://www.tiktok.com/@chef/video/123")

    assert result.platform == "tiktok"
    assert result.description == "Pates creme citron en 10 minutes"
    assert result.author == "chefada"
    assert "tiktok_caption_unavailable" in result.warnings


def test_extract_video_source_tiktok_uses_oembed_and_webvtt(monkeypatch):
    subtitle_url = "https://captions.test/subtitles.vtt"
    html = f"""
    <html>
      <head>
        <meta property="og:title" content="TikTok - Make Your Day" />
        <meta property="og:description" content="Watch more trending videos on TikTok" />
      </head>
      <body>
        <script id="SIGI_STATE" type="application/json">{json.dumps({"ItemModule": {"video-1": {"video": {"subtitleInfos": [{"Url": subtitle_url}]}}}})}</script>
      </body>
    </html>
    """

    class FakeResponse:
        def __init__(self, *, payload=None, text=None):
            self._payload = payload
            self.text = text or ""

        def raise_for_status(self):
            return None

        def json(self):
            if self._payload is None:
                raise ValueError("json payload unavailable")
            return self._payload

    class FakeClient:
        def get(self, url):
            if url.startswith("https://www.tiktok.com/oembed?"):
                return FakeResponse(
                    payload={
                        "title": "Animal fries cajun",
                        "author_name": "Babou",
                        "thumbnail_url": "https://img.test/tiktok-oembed.jpg",
                    }
                )
            if url == subtitle_url:
                return FakeResponse(
                    text=(
                        "WEBVTT\n\n"
                        "00:00:00.000 --> 00:00:01.200\nPremiere etape\n\n"
                        "00:00:01.300 --> 00:00:02.500\nDeuxieme etape\n"
                    )
                )
            raise AssertionError(f"unexpected URL: {url}")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fail_whisper(url: str):  # noqa: ARG001
        raise AssertionError("whisper fallback should not run when subtitles are available")

    monkeypatch.setattr(video_intake, "_fetch_html", lambda url: (html, url))
    monkeypatch.setattr(video_intake, "_http_client", lambda: FakeClient())
    monkeypatch.setattr(video_intake, "_whisper_transcribe", fail_whisper)

    result = video_intake.extract_video_source("https://www.tiktok.com/@chef/video/123")

    assert result.platform == "tiktok"
    assert result.title == "Animal fries cajun"
    assert result.description == "Animal fries cajun"
    assert result.author == "Babou"
    assert result.thumbnail_url == "https://img.test/tiktok-oembed.jpg"
    assert result.transcript == "Premiere etape Deuxieme etape"
    assert result.transcript_source == subtitle_url
    assert len(result.transcript_segments) == 2


def test_extract_video_source_uses_oembed_when_html_fetch_fails(monkeypatch):
    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload
            self.text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeClient:
        def get(self, url):
            assert url.startswith("https://www.youtube.com/oembed?")
            return FakeResponse(
                {
                    "title": "Fallback title",
                    "author_name": "Fallback author",
                    "thumbnail_url": "https://img.test/fallback.jpg",
                }
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(video_intake, "_fetch_html", lambda url: (_ for _ in ()).throw(RuntimeError("html blocked")))  # noqa: ARG005
    monkeypatch.setattr(video_intake, "_http_client", lambda: FakeClient())
    monkeypatch.setattr(
        video_intake,
        "_whisper_transcribe",
        lambda url: ("Fallback transcript", [], "whisper_local:base", []),  # noqa: ARG005
    )

    result = video_intake.extract_video_source("https://www.youtube.com/watch?v=abc123")

    assert result.platform == "youtube"
    assert result.title == "Fallback title"
    assert result.author == "Fallback author"
    assert result.thumbnail_url == "https://img.test/fallback.jpg"
    assert result.transcript == "Fallback transcript"
    assert "html_fetch_failed" in result.warnings




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
