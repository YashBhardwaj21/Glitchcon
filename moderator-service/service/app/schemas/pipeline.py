from pydantic import BaseModel

class KeywordResult(BaseModel):
    decision: str
    matched: str | None = None
    confidence: float
    hint: str | None = None

class PreFilterResult(BaseModel):
    blocked: bool
    stage: str
    matched: str | None = None
    template_key: str | None = None
    detected_language: str | None = None
    keyword_hint: str | None = None
