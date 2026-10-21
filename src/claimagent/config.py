from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
REPORTS_DIR = ROOT / "reports"

DATASET_VERSION = "long-brand-answers-50-v4"
FACT_VERSION = "speaker-catalogue-v4"
EVALUATOR_VERSION = "sentence-spans-and-labels-v4"
MAX_TURNS = 3
MAX_OUTPUT_TOKENS = 8192
VALID_SPLITS = ("development", "check")
VALID_VERSIONS = ("v1", "v2")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    openai_api_key: SecretStr | None = None
    openai_model: str = ""
    database_url: str = "postgresql://claims:claims@localhost:5432/claims"
    request_timeout_s: float = 60
    openai_seed: int = 7


settings = Settings()
