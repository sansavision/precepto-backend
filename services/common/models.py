# common/models.py
from datetime import datetime, timezone
import json
from typing import List, Optional, Any, Annotated
from pydantic import BaseModel, Field, ConfigDict, GetJsonSchemaHandler
from bson import ObjectId
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema

class ObjectIdAnnotation:
    @classmethod
    def validate_object_id(cls, v: Any, handler) -> ObjectId:
        if isinstance(v, ObjectId):
            return v
        
        s = handler(v)
        if ObjectId.is_valid(s):
            return ObjectId(s)
        raise ValueError("Invalid ObjectId")

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type, _handler
    ) -> core_schema.CoreSchema:
        assert source_type is ObjectId
        return core_schema.no_info_wrap_validator_function(
            cls.validate_object_id,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.str_schema())

class BaseModelWithConfig(BaseModel):
    """Base model with common configuration"""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda x: x.isoformat() if x else None
        }
    )

class Entry(BaseModel):
    timestamp: str
    description: str

class Section(BaseModel):
    section: str
    content: List[Entry]

class Note(BaseModel):
    title: str
    content: List[Section]


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)
    
class User(BaseModelWithConfig):
    id: Annotated[ObjectId, ObjectIdAnnotation] = Field(alias="_id")
    name: str
    login_pass: str
    templates: List[str] = Field(default_factory=list)
    is_admin: bool = False
    category: str = "others"
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    logged_in: bool = False

class TranscriptTemplate(BaseModelWithConfig):
    #id: Annotated[ObjectId, ObjectIdAnnotation] = Field(alias="_id")
    id: Annotated[ObjectId, ObjectIdAnnotation] = Field(default=None, alias="_id")
    name: str
    template: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_public: bool = False
    shared_with: List[str] = Field(default_factory=list)

class TranscriptionMeta(BaseModelWithConfig):
    id: Annotated[ObjectId, ObjectIdAnnotation] = Field(alias="_id")
    name: str
    status: str
    backend_status: Optional[str] = None
    template: Optional[str] = None
    audio_url: Optional[str] = None
    transcript: Optional[str] = None
    final_transcript: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    backend_updated_at: Optional[datetime] = None
    duration: Optional[float] = None
    words: Optional[int] = None
    speakers: Optional[int] = None
    confidence: Optional[float] = None
    language: Optional[str] = None
    speaker_labels: Optional[bool] = None
    keywords: Optional[List[str]] = Field(default_factory=list)
    topics: Optional[List[str]] = Field(default_factory=list)
    actions: Optional[List[str]] = Field(default_factory=list)
    translations: Optional[List[str]] = Field(default_factory=list)
    summary: Optional[str] = None
    notes: Optional[str] = None
    marked_for_delete: bool = False
    marked_for_delete_date: Optional[datetime] = None

class SocketMessage(BaseModel):
    id: str
    resource_type: str
    resource_id: str
    status: str
    message: Optional[str] = None