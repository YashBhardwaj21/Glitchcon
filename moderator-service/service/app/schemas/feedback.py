from typing import Optional
from pydantic import BaseModel, Field

class FeedbackTemplateBase(BaseModel):
    template_key: str
    language: str
    message_template: str

class FeedbackTemplateCreate(FeedbackTemplateBase):
    pass

class FeedbackTemplateUpdate(BaseModel):
    message_template: str

class FeedbackTemplateResponse(FeedbackTemplateBase):
    id: int
    
    class Config:
        from_attributes = True
