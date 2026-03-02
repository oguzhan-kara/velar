from pydantic import BaseModel, Field


class STTResult(BaseModel):
    text: str
    language: str                      # "tr" or "en"
    language_probability: float        # 0.0-1.0


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: list[dict] | None = None  # Prior turns: [{"role": "user"|"assistant", "content": str}]
    language: str | None = None        # Override language for TTS; None = auto-detect from response


class ChatResponse(BaseModel):
    text: str
    audio_base64: str                  # MP3 audio as base64
    detected_language: str


class VoiceMetadata(BaseModel):
    transcript: str
    response_text: str
    detected_language: str
