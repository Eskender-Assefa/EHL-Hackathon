from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

Source = Literal[
    "BIMMERPOST", "Bimmerforums", "Reddit", "German_Car_Forum", "Competitor_Web",
    "BMW_Workbook", "BMW_PDF", "Customer_Study", "Sales_Data", "Synthetic",
]
Platform = Literal["F70", "G60", "G70", "Neue_Klasse"]
Category = Literal["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10"]
ScopeLayer = Literal["fixed_now", "variable_later", "hypothetical_later"]
Region = Literal["EU", "CN", "US", "RoW", "Unknown", "Global / Unassigned"]
ClassificationBasis = Literal["bmw_label", "keyword_rule", "llm"]
EffortClass = Literal["software_ux", "interior_trim", "electronics_thermal", "body_platform"]
ReviewBand = Literal["Critical review", "High", "Medium", "Low", "Unscored"]
DecisionStatus = Literal["Proposed", "Approved", "Edited", "Rejected", "Postponed"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(StrictModel):
    source_uri: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    source_platform: Source | None = None
    record_id: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    sheet_name: str | None = None
    row_number: int | None = Field(default=None, ge=1)
    quote: str | None = None


def validate_uri(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https", "bmw-file", "synthetic"}:
        raise ValueError("source URL must be http(s), bmw-file, or synthetic")
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        raise ValueError("web source URL must include a host")
    return value


class FilteredSignal(StrictModel):
    signal_id: str = Field(pattern=r"^[a-zA-Z0-9]+$")
    source_platform: Source
    source_url: str
    timestamp: str | None = Field(default=None, description="ISO 8601 source publication timestamp; null when source is silent")
    target_platform: Platform
    taxonomy_category: Category
    cleaned_verbatim_text: str = Field(min_length=1)
    is_noise: StrictBool = False
    sentiment_score: int = Field(default=0, ge=-100, le=100)
    confidence: float = Field(default=0.5, ge=0, le=1)
    topic: str = "General"
    requirement_statement: str | None = None
    secondary_tags: list[str] = Field(default_factory=list)
    scope_layer: ScopeLayer = "variable_later"
    region: Region = "Unknown"
    country: str | None = None
    source_record_id: str | None = None
    source_score: int | None = None
    author_reputation: int | None = None
    credibility_weight: float = Field(default=1.0, ge=0, le=2)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    feedback_types: list[str] = Field(default_factory=list, description="BMW Feedback Type labels behind this signal")
    classification_basis: ClassificationBasis = "keyword_rule"

    @field_validator("source_url")
    @classmethod
    def valid_source_url(cls, value):
        return validate_uri(value)

    @field_validator("timestamp")
    @classmethod
    def iso_timestamp(cls, value):
        if value is None:
            return value
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Timestamp must include a timezone")
        return value

    @field_validator("cleaned_verbatim_text", "topic")
    @classmethod
    def non_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value


class BmwLabel(StrictModel):
    """One workbook row's own classification: BMW topic and feedback type, kept as a pair."""

    topic: str = Field(min_length=1)
    feedback_type: str = Field(min_length=1)
    subtopic: str | None = None
    row_number: int = Field(ge=1)


class RawPost(StrictModel):
    source_platform: Source
    source_url: str
    thread_title: str
    post_body: str
    timestamp: str | None = None
    score: int | None = None
    author_reputation: int | None = None
    target_platform: Platform | None = None
    collected_at: str
    benchmark_context: str | None = None
    source_record_id: str | None = None
    scope_layer: ScopeLayer = "variable_later"
    region: Region = "Unknown"
    country: str | None = None
    feedback_types: list[str] = Field(default_factory=list)
    original_tags: list[str] = Field(default_factory=list)
    bmw_labels: list[BmwLabel] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    credibility_weight: float = Field(default=1.0, ge=0, le=2)

    @field_validator("source_url")
    @classmethod
    def valid_source_url(cls, value):
        return validate_uri(value)


class Aspect(StrictModel):
    taxonomy_category: Category
    cleaned_verbatim_text: str = Field(min_length=1)
    sentiment_score: int = Field(default=0, ge=-100, le=100)
    confidence: float = Field(default=0.5, ge=0, le=1)
    topic: str = "General"
    requirement_statement: str | None = None
    secondary_tags: list[str] = Field(default_factory=list)
    feedback_types: list[str] = Field(default_factory=list)
    classification_basis: ClassificationBasis = "keyword_rule"

    @field_validator("cleaned_verbatim_text", "topic")
    @classmethod
    def non_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value


class Evaluation(StrictModel):
    is_noise: StrictBool
    reason: str
    aspects: list[Aspect]

    @model_validator(mode="after")
    def consistent(self):
        if self.is_noise and self.aspects:
            raise ValueError("Noise must have no aspects")
        if not self.is_noise and not self.aspects:
            raise ValueError("Accepted text must have aspects")
        return self


class ScoringInputs(StrictModel):
    sales_causality_score: float | None = Field(default=None, ge=0, le=30)
    competitor_roi_score: float | None = Field(default=None, ge=0, le=25)
    effort_class: EffortClass
    assumptions: list[str] = Field(default_factory=list)
    synthetic: bool = False


class RequirementCandidate(StrictModel):
    requirement_id: str = Field(pattern=r"^[A-Z0-9]+$")
    target_platform: Platform
    taxonomy_category: Category
    title: str
    requirement_statement: str
    topic: str
    region_variant: Region
    scope_layer: ScopeLayer
    average_sentiment: float = Field(ge=-100, le=100)
    distinct_signal_count: int = Field(ge=1)
    pain_respondents: int = Field(default=0, ge=0)
    praise_respondents: int = Field(default=0, ge=0)
    current_30d_mentions: int | None = None
    previous_30d_mentions: int | None = None
    velocity_multiplier: float | None = Field(default=None, ge=1, le=3)
    velocity_acceleration_pct: float | None = None
    signal_threshold_score: float = Field(ge=0)
    sales_causality_score: float | None = Field(default=None, ge=0, le=30)
    competitor_roi_score: float | None = Field(default=None, ge=0, le=25)
    effort_class: EffortClass
    effort_penalty: int = Field(ge=0, le=50)
    priority_score: float | None = None
    priority_score_basis: Literal["complete_formula", "static_evidence_proxy"] = "complete_formula"
    partial_priority_score: float
    review_band: ReviewBand
    ehi_score: float = Field(ge=0, le=100)
    groundedness_score: float = Field(ge=0, le=1)
    evidence_volume_score: float = Field(ge=0, le=1)
    market_conflict_penalty: float = Field(ge=0, le=1)
    regional_conflict: bool
    confidence_label: Literal["Verified Evidence", "Medium Evidence", "Uncertain / Conflict Flag"]
    warnings: list[str] = Field(default_factory=list)
    blindspots: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef]
    evidence_source_counts: dict[Source, int] = Field(default_factory=dict)
    status: DecisionStatus = "Proposed"
    pm_rationale: str | None = None
