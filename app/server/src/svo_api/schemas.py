from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9._~-]+$')]
ReviewStatus = Literal['pending', 'confirmed', 'rejected']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class PredictionRequest(StrictModel):
    text: str = Field(min_length=1, max_length=10000)
    event_id: Identifier

    @field_validator('text')
    @classmethod
    def valid_text(cls, value):
        if not value.strip():
            raise ValueError('Text must not be blank')
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError('Text must contain valid Unicode') from None
        return value


class Prediction(StrictModel):
    event_id: str
    scam_score: float
    decision: Literal['high_risk', 'review', 'low_risk']
    needs_review: bool
    novelty_score: float
    is_unknown: bool
    nearest_known_family_or_null: str | None
    cluster_id_or_null: int | None
    model_version: str
    reference_version: str
    scope: str
    cluster_capacity_reached: bool = False


class ReviewRequest(StrictModel):
    review_id: Identifier
    status: ReviewStatus
    actor: str | None = Field(default=None, min_length=1, max_length=80, pattern=r'^[A-Za-z0-9._ -]+$')

    @field_validator('actor')
    @classmethod
    def valid_actor(cls, value):
        if value is not None and not value.strip():
            raise ValueError('Actor must not be blank')
        return value


class ReviewResult(StrictModel):
    review_id: str
    cluster_id: int
    status: ReviewStatus
    actor: str
    actor_verified: bool
    automatic_retraining: Literal[False] = False
    model_version: str


class Cluster(StrictModel):
    cluster_id: int
    unique_text_count: int
    report_count: int
    first_seq: int
    last_seq: int
    status: ReviewStatus
    mean_novelty: float
    candidate_variant: bool
    model_version: str


class ClusterDetail(Cluster):
    representative_event_ids: list[str]


class ClusterPage(StrictModel):
    items: list[Cluster]
    next_after_id: int | None


class ReviewAudit(StrictModel):
    id: int
    cluster_id: int
    status: ReviewStatus
    actor: str
    created: float
    model_version: str
    review_id: str | None
    actor_verified: bool


class ReviewPage(StrictModel):
    items: list[ReviewAudit]
    next_after_id: int | None


class Window(StrictModel):
    end_seq: int
    unknown_fraction: float
    review_fraction: float
    score_mean: float
    alert: bool


class Monitoring(StrictModel):
    model_version: str
    monitoring: str
    latest_window: Window | None
    event_count: int
    cluster_count: int
    pending_count: int
    candidate_count: int
    disk_free_bytes: int
    schema_version: int
