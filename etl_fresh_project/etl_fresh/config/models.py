"""
config/models.py
Pydantic data models aur environment settings.
Week 1 - Day 1-2
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ─────────────────────────────────────────────
# SETTINGS — .env se load hoti hain
# ─────────────────────────────────────────────

class DatabaseSettings(BaseSettings):
    host:     str = Field("localhost",      alias="POSTGRES_HOST")
    port:     int = Field(5432,             alias="POSTGRES_PORT")
    db:       str = Field("data_warehouse", alias="POSTGRES_DB")
    user:     str = Field("postgres",       alias="POSTGRES_USER")
    password: str = Field("etl_password",  alias="POSTGRES_PASSWORD")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def url(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class StripeSettings(BaseSettings):
    secret_key:  str = Field("", alias="STRIPE_SECRET_KEY")
    api_version: str = Field("2023-10-16", alias="STRIPE_API_VERSION")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class SalesforceSettings(BaseSettings):
    client_id:      str = Field("", alias="SALESFORCE_CLIENT_ID")
    client_secret:  str = Field("", alias="SALESFORCE_CLIENT_SECRET")
    username:       str = Field("", alias="SALESFORCE_USERNAME")
    password:       str = Field("", alias="SALESFORCE_PASSWORD")
    security_token: str = Field("", alias="SALESFORCE_SECURITY_TOKEN")
    instance_url:   str = Field("https://login.salesforce.com", alias="SALESFORCE_INSTANCE_URL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class ZendeskSettings(BaseSettings):
    subdomain:  str = Field("", alias="ZENDESK_SUBDOMAIN")
    email:      str = Field("", alias="ZENDESK_EMAIL")
    api_token:  str = Field("", alias="ZENDESK_API_TOKEN")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class PipelineSettings(BaseSettings):
    batch_size:        int = Field(100,   alias="BATCH_SIZE")
    max_retries:       int = Field(3,     alias="MAX_RETRIES")
    log_level:         str = Field("INFO", alias="LOG_LEVEL")
    slack_bot_token:   str = Field("",    alias="SLACK_BOT_TOKEN")
    slack_channel:     str = Field("#etl-alerts", alias="SLACK_CHANNEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class CustomerStatus(str, Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"
    CHURNED  = "churned"
    TRIAL    = "trial"


class PaymentStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED    = "failed"
    PENDING   = "pending"
    REFUNDED  = "refunded"


class TicketStatus(str, Enum):
    OPEN    = "open"
    PENDING = "pending"
    SOLVED  = "solved"
    CLOSED  = "closed"


# ─────────────────────────────────────────────
# UNIFIED DATA MODELS
# ─────────────────────────────────────────────

class UnifiedCustomer(BaseModel):
    """
    Salesforce + Stripe + Zendesk ke customer data ka
    common format. Har source ka data isme map hota hai.
    """
    id:           str
    source:       str                            # stripe / salesforce / zendesk
    source_id:    str
    email:        str
    name:         str
    company:      Optional[str]  = None
    phone:        Optional[str]  = None
    status:       CustomerStatus = CustomerStatus.ACTIVE
    currency:     str            = "USD"
    country:      Optional[str]  = None
    total_spent:  Decimal        = Decimal("0.00")
    created_at:   Optional[datetime] = None
    updated_at:   Optional[datetime] = None
    metadata:     dict           = Field(default_factory=dict)
    extracted_at: datetime       = Field(default_factory=datetime.utcnow)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Email lowercase aur strip karo"""
        return v.strip().lower()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        """Currency uppercase karo"""
        return v.strip().upper()


class UnifiedPayment(BaseModel):
    """Stripe payment/charge ka unified model."""
    id:             str
    source:         str = "stripe"
    source_id:      str
    customer_id:    Optional[str]   = None
    amount:         Decimal
    currency:       str             = "USD"
    status:         PaymentStatus
    description:    Optional[str]   = None
    payment_method: Optional[str]   = None
    created_at:     Optional[datetime] = None
    metadata:       dict            = Field(default_factory=dict)
    extracted_at:   datetime        = Field(default_factory=datetime.utcnow)

    @field_validator("amount", mode="before")
    @classmethod
    def cents_to_dollars(cls, v) -> Decimal:
        """Stripe cents ko dollars mein convert karo (5000 -> 50.00)"""
        return Decimal(str(v)) / 100

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        return v.strip().upper()


class UnifiedTicket(BaseModel):
    """Zendesk support ticket ka unified model."""
    id:                  str
    source:              str = "zendesk"
    source_id:           str
    subject:             str
    description:         Optional[str] = None
    status:              TicketStatus
    priority:            Optional[str] = None
    requester_email:     Optional[str] = None
    assignee_email:      Optional[str] = None
    tags:                List[str]     = Field(default_factory=list)
    created_at:          Optional[datetime] = None
    updated_at:          Optional[datetime] = None
    solved_at:           Optional[datetime] = None
    satisfaction_rating: Optional[str] = None
    metadata:            dict          = Field(default_factory=dict)
    extracted_at:        datetime      = Field(default_factory=datetime.utcnow)
