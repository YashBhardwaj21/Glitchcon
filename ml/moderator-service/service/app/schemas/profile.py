from typing import Optional
from pydantic import BaseModel, Field

class RulesProfileBase(BaseModel):
    group_topic: str
    global_rules: list[str] = Field(default_factory=list)
    group_rules: list[str] = Field(default_factory=list)
    
    supported_languages: list[str] = Field(default=["en", "hi", "ta", "te", "kn", "ml", "hi-en"])
    keywords_by_language: dict[str, list[str]] = Field(default_factory=dict)
    
    spam_limit: int = 5
    spam_window_s: int = 60
    faiss_threshold: float = 0.72
    llm_confidence_threshold_en: float = 0.65
    llm_confidence_threshold_indic: float = 0.60

class RulesProfileCreate(RulesProfileBase):
    profile_id: str

class RulesProfileUpdate(BaseModel):
    group_topic: Optional[str] = None
    global_rules: Optional[list[str]] = None
    group_rules: Optional[list[str]] = None
    supported_languages: Optional[list[str]] = None
    keywords_by_language: Optional[dict[str, list[str]]] = None
    spam_limit: Optional[int] = None
    spam_window_s: Optional[int] = None
    faiss_threshold: Optional[float] = None
    llm_confidence_threshold_en: Optional[float] = None
    llm_confidence_threshold_indic: Optional[float] = None

class RulesProfileResponse(RulesProfileBase):
    id: int
    profile_id: str
    
    class Config:
        from_attributes = True

class KeywordAddRequest(BaseModel):
    word: str
    lang: str
