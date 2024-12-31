# AUTOGENERATED FROM 'common/queries/transcriptions/transcript_read_all.edgeql' WITH:
#     $ edgedb-py --tls-security=insecure -P 5656 -d precepto --dir ./common/queries


from __future__ import annotations
import dataclasses
import datetime
import edgedb
import enum
import uuid


class NoPydanticValidation:
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        # Pydantic 2.x
        from pydantic_core.core_schema import any_schema
        return any_schema()

    @classmethod
    def __get_validators__(cls):
        # Pydantic 1.x
        from pydantic.dataclasses import dataclass as pydantic_dataclass
        _ = pydantic_dataclass(cls)
        cls.__pydantic_model__.__get_validators__ = lambda: []
        return []


@dataclasses.dataclass
class TranscriptReadAllResult(NoPydanticValidation):
    words: int | None
    transcript: str | None
    updated_at: datetime.datetime
    created_at: datetime.datetime
    id: uuid.UUID
    actions: list[str] | None
    audio_url: str | None
    backend_status: TranscriptionBackendStatusType
    backend_updated_at: datetime.datetime | None
    confidence: float | None
    duration: float | None
    final_transcript: str | None
    keywords: list[str] | None
    language: str | None
    marked_for_delete: bool | None
    marked_for_delete_date: datetime.datetime | None
    name: str
    next_backend_step: str | None
    notes: str | None
    place_in_queue: int | None
    speaker_labels: bool | None
    speakers: int | None
    status: TranscriptionStatusType
    summary: str | None
    topics: list[str] | None
    analytics: list[TranscriptReadAllResultAnalyticsItem]
    translations: list[TranscriptReadAllResultTranslationsItem]
    template: TranscriptReadAllResultTemplate
    created_by: TranscriptReadAllResultCreatedBy


@dataclasses.dataclass
class TranscriptReadAllResultAnalyticsItem(NoPydanticValidation):
    updated_at: datetime.datetime
    created_at: datetime.datetime
    id: uuid.UUID
    backend_step: str
    duration: float
    is_success: bool | None


@dataclasses.dataclass
class TranscriptReadAllResultCreatedBy(NoPydanticValidation):
    updated_at: datetime.datetime
    created_at: datetime.datetime
    id: uuid.UUID
    category: str
    email: str | None
    first_name: str | None
    image_url: str | None
    is_admin: bool | None
    last_login: datetime.datetime | None
    last_name: str | None
    logged_in: bool | None
    login_pass: str | None
    user_name: str


@dataclasses.dataclass
class TranscriptReadAllResultTemplate(NoPydanticValidation):
    updated_at: datetime.datetime
    created_at: datetime.datetime
    id: uuid.UUID
    description: str | None
    image_url: str | None
    is_public: bool | None
    name: str
    template: str | None


@dataclasses.dataclass
class TranscriptReadAllResultTranslationsItem(NoPydanticValidation):
    updated_at: datetime.datetime
    created_at: datetime.datetime
    id: uuid.UUID
    language: str
    translation: str


class TranscriptionBackendStatusType(enum.Enum):
    DRAFT = "draft"
    RECORDING_SERVICE = "recording_service"
    TRANSCRIPTION_SERVICE = "transcription_service"
    SUMMARIZATION_SERVICE = "summarization_service"
    COMPLETED = "completed"
    FAILED = "failed"


class TranscriptionStatusType(enum.Enum):
    SIGNED = "signed"
    NOT_SIGNED = "not_signed"
    QUEUED = "queued"
    FAILED = "failed"
    PROCESSING = "processing"
    DRAFT = "draft"


async def transcript_read_all(
    executor: edgedb.AsyncIOExecutor,
    *,
    user_id: uuid.UUID,
) -> list[TranscriptReadAllResult]:
    return await executor.query(
        """\
        # Read a transcription by ID
        SELECT Transcription {**}
        FILTER .created_by.id = <uuid>$user_id;\
        """,
        user_id=user_id,
    )