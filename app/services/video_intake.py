from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from html import unescape
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.schemas import TranscriptSegmentRead, VideoSourceRead

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


def _http_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    )


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = unescape(value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "instagram.com" in host:
        return "instagram"
    if "tiktok.com" in host:
        return "tiktok"
    return "unknown"


def _extract_json_blob(patterns: list[str], html: str) -> dict[str, Any] | None:
    for pattern in patterns:
        match = re.search(pattern, html, re.S)
        if not match:
            continue
        blob = match.group(1)
        try:
            return json.loads(blob)
        except json.JSONDecodeError:
            continue
    return None


def _fetch_html(url: str) -> tuple[str, str]:
    with _http_client() as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text, str(response.url)


def _whisper_config() -> tuple[str, str, str]:
    model_size = os.getenv("ADAMHUB_WHISPER_MODEL", "base").strip() or "base"
    device = os.getenv("ADAMHUB_WHISPER_DEVICE", "cpu").strip() or "cpu"
    compute_type = os.getenv("ADAMHUB_WHISPER_COMPUTE_TYPE", "int8").strip() or "int8"
    return model_size, device, compute_type


@lru_cache(maxsize=4)
def _load_whisper_model(model_size: str, device: str, compute_type: str):
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, device=device, compute_type=compute_type)


def _download_audio_file(url: str) -> tuple[str, str | None, str]:
    import yt_dlp

    tmpdir = tempfile.mkdtemp(prefix="adamhub-audio-")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "ignoreerrors": False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("audio download failed")
        filename = ydl.prepare_filename(info)
        if os.path.exists(filename):
            return filename, info.get("title"), tmpdir
        candidates = sorted(
            (path for path in os.listdir(tmpdir)),
            key=lambda item: os.path.getmtime(os.path.join(tmpdir, item)),
        )
        if not candidates:
            raise RuntimeError("audio file missing after download")
        return os.path.join(tmpdir, candidates[-1]), info.get("title"), tmpdir


def _whisper_transcribe(url: str) -> tuple[str | None, list[TranscriptSegmentRead], str | None, list[str]]:
    warnings: list[str] = []
    tmpdir: str | None = None
    try:
        audio_path, _title, tmpdir = _download_audio_file(url)
    except Exception:
        return None, [], None, ["whisper_audio_download_failed"]

    model_size, device, compute_type = _whisper_config()
    try:
        model = _load_whisper_model(model_size, device, compute_type)
        segments_iter, _info = model.transcribe(audio_path, beam_size=1, vad_filter=True)
        transcript_segments: list[TranscriptSegmentRead] = []
        transcript_parts: list[str] = []
        for segment in segments_iter:
            text = _clean_text(getattr(segment, "text", None))
            if not text:
                continue
            transcript_segments.append(
                TranscriptSegmentRead(
                    start=getattr(segment, "start", None),
                    duration=((getattr(segment, "end", None) - getattr(segment, "start", None)) if getattr(segment, "end", None) is not None and getattr(segment, "start", None) is not None else None),
                    text=text,
                )
            )
            transcript_parts.append(text)
        transcript = _clean_text(" ".join(transcript_parts))
        if not transcript:
            warnings.append("whisper_transcript_empty")
        return transcript, transcript_segments, f"whisper_local:{model_size}", warnings
    except Exception:
        return None, [], None, ["whisper_transcription_failed"]
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def _extract_youtube(html: str, final_url: str) -> VideoSourceRead:
    soup = BeautifulSoup(html, "html.parser")
    player = _extract_json_blob(
        [
            r"var ytInitialPlayerResponse\s*=\s*(\{.*?\});",
            r"ytInitialPlayerResponse\s*=\s*(\{.*?\})\s*;",
        ],
        html,
    )

    video_details = (player or {}).get("videoDetails", {})
    microdata_title = _clean_text(soup.find("meta", attrs={"property": "og:title"})["content"]) if soup.find("meta", attrs={"property": "og:title"}) else None
    microdata_description = _clean_text(soup.find("meta", attrs={"name": "description"})["content"]) if soup.find("meta", attrs={"name": "description"}) else None

    title = _clean_text(video_details.get("title")) or microdata_title
    description = _clean_text(video_details.get("shortDescription")) or microdata_description
    author = _clean_text(video_details.get("author"))
    thumbnail_url = None
    thumbnails = (video_details.get("thumbnail") or {}).get("thumbnails") or []
    if thumbnails:
        thumbnail_url = thumbnails[-1].get("url")

    transcript_segments: list[TranscriptSegmentRead] = []
    transcript_parts: list[str] = []
    transcript_source = None
    warnings: list[str] = []

    caption_tracks = (
        (((player or {}).get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}).get("captionTracks")
        or []
    )
    if caption_tracks:
        track = caption_tracks[0]
        transcript_source = track.get("baseUrl")
        if transcript_source:
            caption_url = transcript_source
            if "fmt=" not in caption_url:
                separator = "&" if "?" in caption_url else "?"
                caption_url = f"{caption_url}{separator}fmt=json3"
            with _http_client() as client:
                try:
                    caption_response = client.get(caption_url)
                    caption_response.raise_for_status()
                    payload = caption_response.json()
                    for event in payload.get("events", []):
                        text = "".join(seg.get("utf8", "") for seg in event.get("segs", []))
                        cleaned = _clean_text(text)
                        if not cleaned:
                            continue
                        transcript_segments.append(
                            TranscriptSegmentRead(
                                start=(event.get("tStartMs") / 1000.0) if event.get("tStartMs") is not None else None,
                                duration=(event.get("dDurationMs") / 1000.0) if event.get("dDurationMs") is not None else None,
                                text=cleaned,
                            )
                        )
                        transcript_parts.append(cleaned)
                except Exception:
                    warnings.append("youtube_caption_fetch_failed")
    else:
        warnings.append("youtube_captions_unavailable")

    transcript = _clean_text(" ".join(transcript_parts))
    if not transcript:
        whisper_transcript, whisper_segments, whisper_source, whisper_warnings = _whisper_transcribe(final_url)
        warnings.extend(whisper_warnings)
        if whisper_transcript:
            transcript = whisper_transcript
            transcript_segments = whisper_segments
            transcript_source = whisper_source

    return VideoSourceRead(
        url=final_url,
        canonical_url=final_url,
        platform="youtube",
        title=title,
        description=description,
        transcript=transcript,
        transcript_source=transcript_source,
        transcript_segments=transcript_segments,
        author=author,
        thumbnail_url=thumbnail_url,
        warnings=warnings,
    )


def _extract_instagram(html: str, final_url: str) -> VideoSourceRead:
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(
        soup.find("meta", attrs={"property": "og:title"})["content"] if soup.find("meta", attrs={"property": "og:title"}) else None
    )
    description = _clean_text(
        soup.find("meta", attrs={"property": "og:description"})["content"] if soup.find("meta", attrs={"property": "og:description"}) else None
    ) or _clean_text(
        soup.find("meta", attrs={"name": "description"})["content"] if soup.find("meta", attrs={"name": "description"}) else None
    )
    thumbnail_url = _clean_text(
        soup.find("meta", attrs={"property": "og:image"})["content"] if soup.find("meta", attrs={"property": "og:image"}) else None
    )
    author = None
    published_at = None
    transcript_segments: list[TranscriptSegmentRead] = []
    warnings: list[str] = []

    caption_match = re.search(r'"edge_media_to_caption":\{"edges":\[\{"node":\{"text":"(.*?)"\}\}\]\}', html, re.S)
    if caption_match:
        transcript = _clean_text(caption_match.group(1))
    else:
        transcript = None
        warnings.append("instagram_caption_unavailable")

    if transcript:
        transcript_segments.append(TranscriptSegmentRead(text=transcript))
    else:
        whisper_transcript, whisper_segments, whisper_source, whisper_warnings = _whisper_transcribe(final_url)
        warnings.extend(whisper_warnings)
        if whisper_transcript:
            transcript = whisper_transcript
            transcript_segments = whisper_segments
            transcript_source = whisper_source

    return VideoSourceRead(
        url=final_url,
        canonical_url=final_url,
        platform="instagram",
        title=title,
        description=description,
        transcript=transcript,
        transcript_source="instagram_caption" if transcript else None,
        transcript_segments=transcript_segments,
        author=author,
        thumbnail_url=thumbnail_url,
        published_at=published_at,
        warnings=warnings,
    )


def _extract_tiktok(html: str, final_url: str) -> VideoSourceRead:
    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(
        soup.find("meta", attrs={"property": "og:title"})["content"] if soup.find("meta", attrs={"property": "og:title"}) else None
    )
    meta_description = _clean_text(
        soup.find("meta", attrs={"property": "og:description"})["content"] if soup.find("meta", attrs={"property": "og:description"}) else None
    ) or _clean_text(
        soup.find("meta", attrs={"name": "description"})["content"] if soup.find("meta", attrs={"name": "description"}) else None
    )
    description = meta_description
    thumbnail_url = _clean_text(
        soup.find("meta", attrs={"property": "og:image"})["content"] if soup.find("meta", attrs={"property": "og:image"}) else None
    )
    author = None
    published_at = None
    transcript_segments: list[TranscriptSegmentRead] = []
    warnings: list[str] = []

    data = _extract_json_blob(
        [
            r"<script id=\"SIGI_STATE\"[^>]*>(\{.*?\})</script>",
            r"window\.__UNIVERSAL_DATA_FOR_REHYDRATION__\s*=\s*(\{.*?\});",
            r"<script id=\"__NEXT_DATA__\"[^>]*>(\{.*?\})</script>",
        ],
        html,
    ) or {}

    video_meta = {}
    if isinstance(data, dict):
        item_module = data.get("ItemModule") or data.get("itemModule") or {}
        if isinstance(item_module, dict) and item_module:
            video_meta = next(iter(item_module.values()), {}) if item_module else {}
        elif "__DEFAULT_SCOPE__" in data:
            default_scope = data.get("__DEFAULT_SCOPE__", {})
            item_module = default_scope.get("webapp.video-detail", {}).get("itemInfo", {}).get("itemStruct", {})
            if isinstance(item_module, dict):
                video_meta = item_module

    structured_description = None
    if isinstance(video_meta, dict):
        structured_description = _clean_text(video_meta.get("desc") or video_meta.get("description"))
    description = structured_description or meta_description

    subtitle_url = None
    if isinstance(video_meta, dict):
        author = _clean_text(
            video_meta.get("author")
            or (video_meta.get("authorInfo") or {}).get("nickname")
            or (video_meta.get("authorInfo") or {}).get("uniqueId")
        )
        subtitle_infos = video_meta.get("video", {}).get("subtitleInfos") or video_meta.get("subtitleInfos") or []
        if subtitle_infos:
            subtitle_url = subtitle_infos[0].get("Url") or subtitle_infos[0].get("url")

    transcript = None
    transcript_source = None
    if subtitle_url:
        with _http_client() as client:
            try:
                subtitle_response = client.get(subtitle_url)
                subtitle_response.raise_for_status()
                payload = subtitle_response.json()
                chunks: list[str] = []
                for item in payload.get("body", payload if isinstance(payload, list) else []):
                    text = item.get("text") if isinstance(item, dict) else None
                    cleaned = _clean_text(text)
                    if cleaned:
                        chunks.append(cleaned)
                        transcript_segments.append(TranscriptSegmentRead(text=cleaned))
                transcript = _clean_text(" ".join(chunks))
                transcript_source = subtitle_url
            except Exception:
                warnings.append("tiktok_subtitle_fetch_failed")
    elif description:
        warnings.append("tiktok_caption_unavailable")

    if not transcript:
        whisper_transcript, whisper_segments, whisper_source, whisper_warnings = _whisper_transcribe(final_url)
        warnings.extend(whisper_warnings)
        if whisper_transcript:
            transcript = whisper_transcript
            transcript_segments = whisper_segments
            transcript_source = whisper_source

    return VideoSourceRead(
        url=final_url,
        canonical_url=final_url,
        platform="tiktok",
        title=title,
        description=description,
        transcript=transcript,
        transcript_source=transcript_source,
        transcript_segments=transcript_segments,
        author=author,
        thumbnail_url=thumbnail_url,
        published_at=published_at,
        warnings=warnings,
    )


def extract_video_source(url: str) -> VideoSourceRead:
    html, final_url = _fetch_html(url)
    platform = _detect_platform(final_url)

    if platform == "youtube":
        return _extract_youtube(html, final_url)
    if platform == "instagram":
        return _extract_instagram(html, final_url)
    if platform == "tiktok":
        return _extract_tiktok(html, final_url)

    soup = BeautifulSoup(html, "html.parser")
    title = _clean_text(soup.find("meta", attrs={"property": "og:title"})["content"]) if soup.find("meta", attrs={"property": "og:title"}) else None
    description = _clean_text(soup.find("meta", attrs={"name": "description"})["content"]) if soup.find("meta", attrs={"name": "description"}) else None
    thumbnail_url = _clean_text(soup.find("meta", attrs={"property": "og:image"})["content"]) if soup.find("meta", attrs={"property": "og:image"}) else None
    whisper_transcript, whisper_segments, whisper_source, whisper_warnings = _whisper_transcribe(final_url)
    return VideoSourceRead(
        url=final_url,
        canonical_url=final_url,
        platform=platform,
        title=title,
        description=description,
        transcript=whisper_transcript,
        transcript_source=whisper_source,
        transcript_segments=whisper_segments,
        thumbnail_url=thumbnail_url,
        warnings=[f"unsupported_platform:{platform}", *whisper_warnings],
    )
