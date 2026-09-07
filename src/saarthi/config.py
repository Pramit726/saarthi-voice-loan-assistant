from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Server-side configuration. Provider secrets never cross the API boundary."""

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Saarthi Voice Loan Assistant"
    environment: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    livekit_url: str = ""
    livekit_api_key: SecretStr = SecretStr("")
    livekit_api_secret: SecretStr = SecretStr("")
    livekit_agent_name: str = "saarthi"
    livekit_token_ttl_seconds: int = 900

    deepgram_api_key: SecretStr = SecretStr("")
    deepgram_model: str = "flux-general-en"
    deepgram_numerals: bool = True
    deepgram_eot_timeout_ms: int = 1200

    # LiveKit barge-in tuning. A short VAD blip should not stop a response;
    # explicit stop is still handled separately by the worker.
    interruption_min_duration_seconds: float = 0.50
    interruption_min_words: int = 1
    false_interruption_timeout_seconds: float = 1.50
    # Minimum final-transcript-to-playback handoff. Fast deterministic turns
    # need this; slow provider turns have already consumed the interval.
    post_transcript_settle_delay_seconds: float = 0.65
    interrupted_response_recovery_delay_seconds: float = 1.75
    interrupted_response_max_retries: int = 1

    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-120b"
    groq_timeout_seconds: float = 12.0
    groq_temperature: float = 0.0
    grounded_llm_wording_enabled: bool = False

    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_timeout_seconds: float = 12.0

    rime_api_key: SecretStr = SecretStr("")
    # Coda is the current Rime conversational model. The configured Rime
    # account accepts the Nadi/Coda pairing for both selected languages.
    rime_model: str = "coda"
    rime_english_speaker: str = "nadi"
    rime_hindi_speaker: str = "nadi"
    # Rime's newer models use speedAlpha values below 1.0 for a slightly
    # slower delivery. This is passed through the websocket plugin.
    rime_speed_alpha: float = 0.92
    rime_sample_rate: int = 24000

    qdrant_url: str = ""
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection: str = "loan_product_facts"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    retrieval_limit: int = 5
    retrieval_score_threshold: float = 0.35

    database_url: str = "sqlite+aiosqlite:///./data/saarthi.db"
    redis_url: str = ""
    product_facts_path: Path = Field(
        default=REPOSITORY_ROOT / "data" / "product" / "saarthi_product_facts_v1.json"
    )

    normal_turn_first_audio_target_ms: int = 3000
    grounded_turn_first_audio_target_ms: int = 5000
    stop_latency_target_ms: int = 500

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def missing_required_providers(self) -> list[str]:
        required = {
            "LIVEKIT_URL": self.livekit_url,
            "LIVEKIT_API_KEY": self.livekit_api_key.get_secret_value(),
            "LIVEKIT_API_SECRET": self.livekit_api_secret.get_secret_value(),
            "DEEPGRAM_API_KEY": self.deepgram_api_key.get_secret_value(),
            "GROQ_API_KEY": self.groq_api_key.get_secret_value(),
            "GEMINI_API_KEY": self.gemini_api_key.get_secret_value(),
            "RIME_API_KEY": self.rime_api_key.get_secret_value(),
            "QDRANT_URL": self.qdrant_url,
            "QDRANT_API_KEY": self.qdrant_api_key.get_secret_value(),
        }
        return [name for name, value in required.items() if not value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
