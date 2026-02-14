"""
core/types.py — Semantic domain types.
Every domain value uses one of these types. They carry validation and documentation.
Import these EVERYWHERE — never use raw str/int for domain values.
"""
from __future__ import annotations

import re
import uuid
from datetime import time
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field


# ─── Identity Types ───
def _validate_uuid(v: Any) -> uuid.UUID:
    if isinstance(v, uuid.UUID):
        return v
    return uuid.UUID(str(v))


TenantId = Annotated[
    uuid.UUID,
    BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for an insurer tenant"),
]
AgentId = Annotated[
    uuid.UUID,
    BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for an insurance agent"),
]
ADMId = Annotated[
    uuid.UUID,
    BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for an ADM user"),
]
UserId = Annotated[
    uuid.UUID,
    BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for any platform user"),
]
SignalId = Annotated[
    uuid.UUID,
    BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for a signal event"),
]
ConversationId = Annotated[
    uuid.UUID,
    BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for a conversation thread"),
]
PlaybookId = Annotated[
    uuid.UUID,
    BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for a playbook definition"),
]
RegionNodeId = Annotated[
    uuid.UUID,
    BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for a node in region hierarchy"),
]
TrainingModuleId = Annotated[
    uuid.UUID,
    BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for a training module"),
]


# ─── Personal Information Types ───
def _validate_indian_mobile(v: str) -> str:
    cleaned = re.sub(r"[\s\-\(\)]", "", str(v))
    if cleaned.startswith("0"):
        cleaned = "+91" + cleaned[1:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = "+" + cleaned
    elif len(cleaned) == 10 and cleaned[0] in "6789":
        cleaned = "+91" + cleaned
    if not re.match(r"^\+91[6-9]\d{9}$", cleaned):
        raise ValueError(f"Invalid Indian mobile number: {v}")
    return cleaned


IndianMobileNumber = Annotated[
    str,
    AfterValidator(_validate_indian_mobile),
    Field(
        description="Indian mobile number in E.164 (+91XXXXXXXXXX)",
        json_schema_extra={"pattern": r"^\+91[6-9]\d{9}$"},
    ),
]


def _validate_email(v: str) -> str:
    v = str(v).strip().lower()
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
        raise ValueError(f"Invalid email: {v}")
    return v


EmailAddress = Annotated[
    str,
    AfterValidator(_validate_email),
    Field(description="Email address, normalized to lowercase"),
]


def _validate_pan(v: str) -> str:
    v = str(v).strip().upper()
    if not re.match(r"^[A-Z]{5}\d{4}[A-Z]$", v):
        raise ValueError(f"Invalid PAN: {v}")
    return v


IndianPAN = Annotated[
    str,
    AfterValidator(_validate_pan),
    Field(description="Indian PAN. PII — encrypt at rest."),
]


def _validate_aadhaar(v: str) -> str:
    v = re.sub(r"[\s\-]", "", str(v))
    if not re.match(r"^\d{12}$", v):
        raise ValueError("Invalid Aadhaar: must be 12 digits")
    return v


AadhaarNumber = Annotated[
    str,
    AfterValidator(_validate_aadhaar),
    Field(description="Aadhaar (12 digits). PII — encrypt, never display full."),
]

PersonName = Annotated[str, Field(max_length=200, description="Full name")]
AgentCode = Annotated[str, Field(max_length=50, description="Agent code from insurer PAS")]
IrdaiLicenseNumber = Annotated[str, Field(max_length=50, description="IRDAI license number")]
ProductCode = Annotated[str, Field(max_length=50, description="Product code from insurer catalog")]


# ─── Monetary Types ───
class Money(BaseModel):
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")

    def __str__(self) -> str:
        return f"\u20b9{self.amount:,.2f}"


# ─── Temporal Types ───
class TimeWindow(BaseModel):
    start: time
    end: time
    timezone: str = Field(default="Asia/Kolkata")

    def contains(self, t: time) -> bool:
        if self.start <= self.end:
            return self.start <= t <= self.end
        return t >= self.start or t <= self.end


# ─── Language ───
SUPPORTED_LANGUAGES = {"hi", "en", "ta", "te", "kn", "mr", "bn", "ml", "gu", "pa", "or", "as"}


def _validate_language(v: str) -> str:
    v = str(v).lower().strip()
    if v not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {v}")
    return v


Language = Annotated[
    str,
    AfterValidator(_validate_language),
    Field(description="ISO 639-1 language code"),
]
