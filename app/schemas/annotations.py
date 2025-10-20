import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.common.enum import AnnotationType
from app.models.annotation_model import DocumentAnnotationBase

# ==============================
# DOCUMENT ANNOTATIONS SCHEMAS
# ==============================

# class DocumentAnnotationBase(BaseModel):
#     type: AnnotationType
#     page_number: Optional[int] = None
#     content: Optional[str] = None
#     meta_data: Optional[dict[str, Any]] = None
#     is_shared: bool = False


class DocumentAnnotationCreate(DocumentAnnotationBase):
    document_id: uuid.UUID


class DocumentAnnotationRead(DocumentAnnotationBase):
    id: uuid.UUID
    account_id: uuid.UUID
    document_id: uuid.UUID
    created_at: datetime


# ==============================
# DOCUMENT CHAT SCHEMAS
# ==============================
class ChatMessage(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str


class DocumentChatBase(BaseModel):
    messages: list[ChatMessage]
    last_message_at: datetime


class DocumentChatCreate(BaseModel):
    document_id: uuid.UUID
    messages: list[ChatMessage]


class DocumentChatRead(DocumentChatBase):
    id: uuid.UUID
    document_id: uuid.UUID
    account_id: uuid.UUID
    created_at: datetime
