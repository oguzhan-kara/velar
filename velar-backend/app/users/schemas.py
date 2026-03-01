from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class UserProfile(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    created_at: datetime
