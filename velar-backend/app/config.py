from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    database_url: str  # postgresql+asyncpg://...
    environment: str = "development"
    debug: bool = False

    # Voice pipeline (Phase 2)
    anthropic_api_key: str = ""          # Required for Claude conversation
    elevenlabs_api_key: str = ""         # Required for ElevenLabs TTS; empty = Edge TTS only
    whisper_model_size: str = "large-v3-turbo"  # STT model size

    # Memory system (Phase 3)
    openai_api_key: str = ""  # Required for embeddings; empty = memory endpoints fail


settings = Settings()
