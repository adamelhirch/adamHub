from datetime import datetime
from pydantic import BaseModel, Field


class ChatMessageTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., max_length=20000)


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: str | None = None
    history: list[ChatMessageTurn] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)


class UserProfileRead(BaseModel):
    id: int
    user_id: int
    dietary_preferences: list[str] = Field(default_factory=list)
    fitness_goals: str = ""
    lifestyle_notes: str = ""
    ai_tone: str = "direct"
    onboarding_completed: bool = False
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    dietary_preferences: list[str] | None = None
    fitness_goals: str | None = None
    lifestyle_notes: str | None = None
    ai_tone: str | None = None
    onboarding_completed: bool | None = None


class UserMemoryRead(BaseModel):
    id: int
    user_id: int
    category: str
    fact: str
    confidence: float = 1.0
    source: str = "conversation"
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class UserMemoryCreate(BaseModel):
    category: str = Field(default="lifestyle", max_length=50)
    fact: str = Field(..., min_length=1, max_length=1000)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class UserMemoryUpdate(BaseModel):
    category: str | None = None
    fact: str | None = None
    is_active: bool | None = None


class AssistantSessionResetResponse(BaseModel):
    ok: bool = True


class AudioTranscribeRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64 encoded audio bytes")
    mime_type: str = Field(default="audio/webm", description="MIME type of the audio (e.g. audio/webm, audio/mp4, audio/wav)")


class AudioTranscribeResponse(BaseModel):
    text: str = Field(..., description="Transcribed text from the audio")

