from pydantic import BaseModel

class PreFilterResult(BaseModel):
    blocked: bool
    stage: str
    matched: str | None = None
    template_key: str | None = None
    detected_language: str | None = None
