from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


VALID_ENTRY_TYPES = ["thesis", "note", "entry", "exit", "adjustment", "review"]


class JournalEntryCreate(BaseModel):
    entry_type: str = Field(default="note", pattern="^(thesis|note|entry|exit|adjustment|review)$")
    content: str = Field(..., min_length=1)


class JournalEntryUpdate(BaseModel):
    entry_type: Optional[str] = Field(default=None, pattern="^(thesis|note|entry|exit|adjustment|review)$")
    content: Optional[str] = Field(default=None, min_length=1)


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    watchlist_id: UUID
    entry_type: str
    content: str
    created_at: datetime
    updated_at: datetime
