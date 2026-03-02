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

    # Integration tools (Phase 4)
    google_calendar_credentials_path: str = "~/.velar/google_credentials.json"
    openweathermap_api_key: str = ""   # One Call by Call subscription required
    weather_city: str = "Istanbul"     # User's city for weather/places (set once)
    google_places_api_key: str = ""    # Places API (New) key
    places_city: str = "Istanbul"      # City for place searches

    # Free-tier provider selection (Phase 5)
    # TTS: "edge" (default, free) or "elevenlabs" (paid, higher quality)
    tts_provider: str = "edge"
    # LLM: "gemini" (default, free tier) or "anthropic" (paid, Claude Haiku)
    llm_provider: str = "gemini"
    # Embeddings: "local" (default, sentence-transformers, no API key) or "openai" (paid)
    embedding_provider: str = "local"

    # Google AI (Gemini) — free at aistudio.google.com
    google_ai_api_key: str = ""

    # Groq — free at console.groq.com (Llama 3.3 70B)
    groq_api_key: str = ""

    # Local embedding model configuration
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"  # 384 dims, Turkish-native
    embedding_dims: int = 384  # 384 for local/sentence-transformers, 1536 for openai

    @property
    def resolved_embedding_dims(self) -> int:
        """Return the correct embedding dimension based on the active provider."""
        if self.embedding_provider == "openai":
            return 1536
        return 384  # local sentence-transformers default


settings = Settings()
