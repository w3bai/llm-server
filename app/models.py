from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CompetitionCreate(BaseModel):
    name: str
    github_url: str
    docs_url: Optional[str] = None

class CompetitionResponse(BaseModel):
    id: str
    name: str
    github_url: str
    docs_url: Optional[str] = None
    created_at: datetime

class Query(BaseModel):
    competition_id: str
    question: str