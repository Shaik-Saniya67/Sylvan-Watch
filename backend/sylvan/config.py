"""Runtime configuration. All values come from environment variables (prefix SYLVAN_) or .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SYLVAN_", extra="ignore")

    storage_dir: Path = Path("storage")

    # Google Earth Engine credentials (either interactive auth or a service account).
    ee_project: str | None = None
    ee_service_account: str | None = None
    ee_private_key_file: Path | None = None

    # Dataset identifiers. Verify them against the Earth Engine catalogue before training:
    # Hansen publishes a new version roughly once per year.
    s2_asset: str = "COPERNICUS/S2_SR_HARMONIZED"
    hansen_asset: str = "UMD/hansen/global_forest_change_2024_v1_12"
    worldcover_asset: str = "ESA/WorldCover/v200"

    tree_cover_threshold: int = 30     # % canopy in 2000 that defines "forest" (Hansen convention)
    max_cloud_percent: float = 60.0    # scene-level pre-filter before pixel-level SCL masking
    max_aoi_km: float = 15.0           # per-side limit for interactive detection
    min_detection_ha: float = 0.5      # polygons smaller than this are dropped
    cors_origins: list[str] = ["http://localhost:3000","http://localhost:3001"]

    @property
    def chips_dir(self) -> Path:
        return self.storage_dir / "chips"

    @property
    def models_dir(self) -> Path:
        return self.storage_dir / "models"

    @property
    def results_dir(self) -> Path:
        return self.storage_dir / "results"

    @property
    def runs_dir(self) -> Path:
        return self.storage_dir / "runs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
