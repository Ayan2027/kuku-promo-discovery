
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


SegmentType = Literal[
    "CAMERA",
    "ACTION",
    "SOUND FX",
    "DIALOGUE",
    "OTHER"
]


class Segment(BaseModel):
    segment_id: str
    episode_number: int
    scene_id: str

    segment_type: SegmentType
    speaker: Optional[str] = None
    emotion_or_direction: Optional[str] = None

    start_timestamp: str
    end_timestamp: str

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)

    content: str
    source_file: str
    source_line: Optional[int] = None

    @model_validator(mode="after")
    def validate_interval(self):
        if self.end_seconds <= self.start_seconds:
            raise ValueError(
                "Segment end must be greater than segment start."
            )
        return self


class Scene(BaseModel):
    scene_id: str
    episode_number: int

    scene_heading: str
    location: Optional[str] = None
    time_of_day: Optional[str] = None

    start_timestamp: str
    end_timestamp: str

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)

    segment_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scene_interval(self):
        if self.end_seconds <= self.start_seconds:
            raise ValueError(
                "Scene end must be greater than scene start."
            )
        return self


class Episode(BaseModel):
    episode_number: int
    source_file: str

    logline: str
    continuity_notes: str

    scenes: list[Scene] = Field(default_factory=list)
    segments: list[Segment] = Field(default_factory=list)

    duration_seconds: float = Field(default=0, ge=0)

    raw_text: str = ""


class PromoScoreBreakdown(BaseModel):
    hook_strength: float = Field(ge=0, le=10)
    emotional_impact: float = Field(ge=0, le=10)
    suspense_curiosity: float = Field(ge=0, le=10)
    cliffhanger_payoff: float = Field(ge=0, le=10)
    standalone_clarity: float = Field(ge=0, le=10)
    promotional_relevance: float = Field(ge=0, le=10)

    final_score: float = Field(ge=0, le=10)


class SourceSegment(BaseModel):
    """A source screenplay segment included in a promo, with exact timing."""

    segment_id: str
    scene_id: Optional[str] = None
    segment_type: str
    speaker: Optional[str] = None
    start_timestamp: str
    end_timestamp: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    content: str


class PromoCandidate(BaseModel):
    promo_id: str
    title: str

    episode_number: int

    start_timestamp: str
    end_timestamp: str

    start_seconds: float
    end_seconds: float
    duration_seconds: float

    opening_hook: str
    main_dramatic_moment: str
    ending_cliffhanger_or_payoff: str
    promotional_justification: str

    dialogue: list[str] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)

    emotional_category: str

    source_segment_ids: list[str] = Field(default_factory=list)

    # Complete ordered source segments, so the export is self-contained.
    source_segments: list[SourceSegment] = Field(default_factory=list)

    # Human-readable explanation of the editorial choice.
    hook_type: str = "unknown"
    cliffhanger_type: str = "unknown"
    why_it_works: str = ""

    analysis_mode: str = "DETERMINISTIC_FALLBACK"

    score_breakdown: Optional[PromoScoreBreakdown] = None

    validation_status: str = "PENDING"
    validation_issues: list[str] = Field(default_factory=list)

    human_review_label: Optional[str] = None
    rank_reason: str = ""


class DatasetSummary(BaseModel):
    total_episodes: int = 0
    processed_episodes: int = 0
    failed_episodes: int = 0

    total_scenes: int = 0
    total_segments: int = 0

    dialogue_segments: int = 0
    camera_segments: int = 0
    action_segments: int = 0
    sound_segments: int = 0

    missing_timestamps: int = 0
    invalid_timestamps: int = 0
    parsing_errors: list[str] = Field(default_factory=list)
