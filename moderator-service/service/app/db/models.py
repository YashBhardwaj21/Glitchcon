from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class RulesProfile(Base):
    __tablename__ = "rules_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(String, unique=True, index=True, nullable=False)
    group_topic = Column(String, nullable=False)
    
    global_rules = Column(JSONB, default=list)
    group_rules = Column(JSONB, default=list)
    
    supported_languages = Column(ARRAY(Text), default=["en", "hi", "ta", "te", "kn", "ml", "hi-en"])
    keywords_by_language = Column(JSONB, default=dict)
    
    spam_limit = Column(Integer, default=5)
    spam_window_s = Column(Integer, default=60)
    faiss_threshold = Column(Float, default=0.72)
    llm_confidence_threshold_en = Column(Float, default=0.65)
    llm_confidence_threshold_indic = Column(Float, default=0.60)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BannedTopicEmbedding(Base):
    __tablename__ = "banned_topic_embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(String, ForeignKey("rules_profiles.profile_id"), index=True, nullable=False)
    topic_label = Column(String, nullable=False)
    embedding = Column(ARRAY(Float), nullable=False)  # 384-dim
    
    created_at = Column(DateTime, default=datetime.utcnow)

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    app_name = Column(String, nullable=False)
    key_hash = Column(String, unique=True, nullable=False)
    profile_id_whitelist = Column(ARRAY(Text), default=list)
    is_active = Column(Boolean, default=True)
    rate_limit_per_min = Column(Integer, default=60)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

class ModerationLog(Base):
    __tablename__ = "moderation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), index=True, nullable=False)
    profile_id = Column(String, index=True, nullable=False)
    message_hash = Column(String, index=True, nullable=False)
    
    decision = Column(String, nullable=False)  # ALLOW or BLOCK
    detected_language = Column(String)         # e.g., "en", "hi-en"
    stage_triggered = Column(String)           # e.g., "stage1_keyword", "llm"
    violated_rule = Column(String)
    confidence = Column(Float)
    
    latency_stage0_ms = Column(Integer, default=0)
    latency_stage1_ms = Column(Integer, default=0)
    latency_stage2_ms = Column(Integer, default=0)
    latency_stage3_ms = Column(Integer, default=0)
    total_latency_ms = Column(Integer, default=0)
    
    llm_provider = Column(String)              # "groq", "gemini", etc.
    created_at = Column(DateTime, default=datetime.utcnow)

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(String, ForeignKey("rules_profiles.profile_id"), index=True, nullable=True) # null = global
    template_text = Column(String, nullable=False)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FeedbackTemplate(Base):
    __tablename__ = "feedback_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_type = Column(String, nullable=False, index=True)
    language_code = Column(String, nullable=False, index=True)
    template_text = Column(String, nullable=False)
    is_default = Column(Boolean, default=False)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LLMProviderLog(Base):
    __tablename__ = "llm_provider_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(String)
    
    created_at = Column(DateTime, default=datetime.utcnow)
