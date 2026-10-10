from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Source = Literal["BIMMERPOST", "Bimmerforums", "Reddit", "German_Car_Forum", "Competitor_Web"]
Platform = Literal["F70", "G60", "G70", "Neue_Klasse"]
Category = Literal["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FilteredSignal(StrictModel):
    signal_id: str = Field(pattern=r"^[a-zA-Z0-9]+$")
    source_platform: Source
    source_url: str
    timestamp: str = Field(description="ISO 8601 source publication timestamp")
    target_platform: Platform
    taxonomy_category: Category
    cleaned_verbatim_text: str = Field(min_length=1)
    is_noise: bool = False

    @field_validator("timestamp")
    @classmethod
    def iso_timestamp(cls, value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Timestamp must include a timezone")
        return value


class RawPost(StrictModel):
    source_platform: Source
    source_url: str
    thread_title: str
    post_body: str
    timestamp: str | None = None
    score: int | None = None
    target_platform: Platform | None = None
    collected_at: str
    benchmark_context: str | None = None


class Aspect(StrictModel):
    taxonomy_category: Category
    cleaned_verbatim_text: str = Field(min_length=1)


class Evaluation(StrictModel):
    is_noise: bool
    reason: str
    aspects: list[Aspect]

    @model_validator(mode="after")
    def consistent(self):
        if self.is_noise and self.aspects:
            raise ValueError("Noise must have no aspects")
        if not self.is_noise and not self.aspects:
            raise ValueError("Accepted text must have aspects")
        return self
