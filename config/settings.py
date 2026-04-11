"""
airavat digital twin engine — configuration
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    stream_maxlen: int = 50_000

    # Raw stream names (Tier 1 → Tier 2)
    stream_bank: str = "stream:bank_transactions"
    stream_upi: str = "stream:upi_transactions"
    stream_sms: str = "stream:sms_alerts"
    stream_emi: str = "stream:recurring_schedules"
    stream_ob: str = "stream:open_banking"
    stream_voice: str = "stream:voice_transcripts"

    # Typed event stream (Tier 2 → Tier 3)
    stream_typed: str = "stream:typed_events"

    # Feature stream (Tier 3 → Tier 4)
    stream_features: str = "stream:behavioural_features"

    # Consumer groups
    cg_classifier: str = "cg_classifier"
    cg_feature_engine: str = "cg_feature_engine"

    # Data paths
    raw_data_path: str = "data/raw"
    features_path: str = "data/features"
    models_path: str = "data/models"

    # Synthetic generator
    n_profiles: int = 100
    history_months: int = 12

    # Tier 2 classifier
    embedding_model: str = "all-MiniLM-L6-v2"
    similarity_threshold: float = 0.50
    lru_cache_size: int = 4096

    # Tier 3 feature engine
    peer_cohort_path: str = "data/features/peer_cohorts.parquet"

    # LLM (OpenRouter)
    openrouter_api_key: str = ""
    llm_model: str = "google/gemma-3-4b-it:free"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
