from typing import Optional
from pydantic import BaseModel, Field

class FeedbackTemplateBase(BaseModel):
    rule_type: str
    language_code: str
    template_text: str

class FeedbackTemplateCreate(FeedbackTemplateBase):
    pass

class FeedbackTemplateUpdate(BaseModel):
    template_text: str

class FeedbackTemplateResponse(FeedbackTemplateBase):
    id: int
    
    class Config:
        from_attributes = True
