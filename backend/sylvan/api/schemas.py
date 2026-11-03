"""Request/response models (also drive the OpenAPI docs at /docs)."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ModelChoice = Literal["best", "spectral_baseline", "random_forest", "siamese_unet"]


class DetectionIn(BaseModel):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-85, le=85)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-85, le=85)
    before_year: int = Field(ge=2018, le=2030, description="Sentinel-2 L2A is globally available from 2018 onwards.")
    after_year: int = Field(ge=2018, le=2030)
    season_start_month: int = Field(ge=1, le=12)
    season_end_month: int = Field(ge=1, le=12)
    model: ModelChoice = "best"

    @model_validator(mode="after")
    def _check_order(self) -> "DetectionIn":
        if self.after_year <= self.before_year:
            raise ValueError("after_year must be later than before_year.")
        if self.season_end_month < self.season_start_month:
            raise ValueError("The season must lie within one calendar year (end month >= start month).")
        return self


class RunCreated(BaseModel):
    id: str
