# models.py
import json
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict
from pydantic import BaseModel



class Entry(BaseModel):
    timestamp: str
    description: str

    def to_json(self):
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data):
        return Entry(**json.loads(data))

    def to_dict(self):
        return asdict(self)

class Section(BaseModel):
    section: str
    content: List[Entry]

    def to_json(self):
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data):
        return Section(**json.loads(data))

    def to_dict(self):
        return asdict(self)

class Note(BaseModel):
    title: str
    content: List[Section]

    def to_json(self):
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data):
        return Note(**json.loads(data))

    def to_dict(self):
        return asdict(self)
    


@dataclass
class User:
    id: str
    name: str
    login_pass: str  # Hashed password
    templates: List[str]
    last_login: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    logged_in: bool = False

    def to_json(self):
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data):
        return User(**json.loads(data))


@dataclass
class TranscriptTemplate:
    id: str
    name: str
    template: str
    created_by_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_public: bool = False
    shared_with: List[str] = field(default_factory=list)

    def to_json(self):
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data):
        return TranscriptTemplate(**json.loads(data))
    
    def to_dict(self):
        return asdict(self)
# @dataclass
# class TranscriptTemplate:
#     id: str
#     name: str
#     template: str
#     created_by_id: str

#     def to_json(self):
#         return json.dumps(asdict(self))

#     @staticmethod
#     def from_json(data):
#         return TranscriptTemplate(**json.loads(data))


@dataclass
class TranscriptionMeta:
    id: str
    name: str
    status: str
    backend_status: Optional[str] = None
    template_id: Optional[str] = None
    audio_url: Optional[str] = None
    transcript: Optional[str] = None
    final_transcript: Optional[str] = None
    created_at: Optional[str] = None
    created_by_id: Optional[str] = None
    updated_at: Optional[str] = None
    backend_updated_at: Optional[str] = None
    duration: Optional[float] = None
    words: Optional[int] = None
    speakers: Optional[int] = None
    confidence: Optional[float] = None
    language: Optional[str] = None
    speaker_labels: Optional[bool] = None
    keywords: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    actions: Optional[List[str]] = None
    translations: Optional[List[str]] = None
    summary: Optional[str] = None
    notes: Optional[str] = None

    def to_json(self):
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data):
        return TranscriptionMeta(**json.loads(data))
    
    def to_dict(self):
        return asdict(self)
@dataclass
class TranscriptionMetaOld:
    id: str
    name: str
    status: str  # 'complete' | 'incomplete' | 'queued'
    backend_status: Optional[str] = None
    template_id: Optional[str] = None
    audio_url: Optional[str] = None
    transcript: Optional[str] = None
    final_transcript: Optional[str] = None
    created_at: Optional[str] = None
    created_by_id: Optional[str] = None
    updated_at: Optional[str] = None
    backend_updated_at: Optional[str] = None
    duration: Optional[float] = None
    words: Optional[int] = None
    speakers: Optional[int] = None
    confidence: Optional[float] = None
    language: Optional[str] = None
    speaker_labels: Optional[bool] = None
    keywords: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    actions: Optional[List[str]] = None
    translations: Optional[List[str]] = None
    summary: Optional[str] = None
    notes: Optional[str] = None

    def to_json(self):
        return json.dumps(asdict(self), default=str)

    @staticmethod
    def from_json(data):
        return TranscriptionMeta(**json.loads(data))

@dataclass
class SocketMessage:
    id: str
    resource_type: str  # 'transcription'
    resource_id: str
    status: str  # 'success' | 'error'
    message: Optional[str] = None

    def to_json(self):
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data):
        return SocketMessage(**json.loads(data))
