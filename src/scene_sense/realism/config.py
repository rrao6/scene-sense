"""Runtime config for the realism pipeline."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class RealismConfig:
    gemini_api_key: str
    gemini_model_fast: str = "gemini-2.5-flash"
    gemini_model_deep: str = "gemini-2.5-pro"

    cache_dir: Path = field(default_factory=lambda: Path(".cache/realism"))
    outputs_dir: Path = field(default_factory=lambda: Path("data/outputs"))
    source_bank_dir: Path = field(default_factory=lambda: Path("data/outputs/source_banks"))

    request_timeout_s: int = 60
    http_timeout_s: int = 20
    quote_match_threshold: float = 0.92
    quote_validator_threshold: float = 0.88
    min_scene_duration_s: float = 15.0

    enable_cache: bool = True

    def ensure_dirs(self) -> None:
        for d in (self.cache_dir, self.outputs_dir, self.source_bank_dir):
            d.mkdir(parents=True, exist_ok=True)


def load_config(env_path: Path | str | None = None) -> RealismConfig:
    if env_path is not None:
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not found in environment or .env")

    cfg = RealismConfig(
        gemini_api_key=key,
        enable_cache=os.environ.get("ENABLE_ANALYSIS_CACHE", "true").lower() == "true",
    )
    cfg.ensure_dirs()
    return cfg
