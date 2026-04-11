"""
Canonical financial event schema — the unified output of Tier 1.

Every raw source (bank, UPI, SMS, EMI, open-banking, voice) is normalised
into a CanonicalEvent before being pushed to stream:typed_events (Tier 2).

Design principles (from tier1.md / schema.md):
  - UUID idempotency on event_id
  - ISO 8601 timestamps (stored as datetime)
  - Source provenance tag on every event
  - PII minimised: user_id is a hashed key, no real names
  - Signed amounts: positive = inflow, negative = outflow
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── enumerations ─────────────────────────────────────────────────────────────

SourceProvenance = Literal[
    "bank_api",
    "upi_api",
    "sms_parser",
    "emi_statement",
    "open_banking_aa",
    "voice_stt_parser",
    "gst_portal",
    "eway_bill_nic",
]

ChannelEnum = Literal["BANK_TRANSFER", "UPI", "CARD", "ATM", "EMI", "OTHER"]

StatusEnum = Literal["SUCCESS", "PENDING", "FAILED"]

TransactionTypeEnum = Literal[
    "INCOME",
    "EXPENSE_ESSENTIAL",
    "EXPENSE_DISCRETIONARY",
    "EMI_PAYMENT",
    "SUBSCRIPTION",
    "TRANSFER",
    "INVESTMENT",
    "REFUND",
    "OTHER",
]

MerchantCategoryEnum = Literal[
    "SALARY",
    "GROCERY",
    "TRANSPORT",
    "DINING",
    "HEALTHCARE",
    "ENTERTAINMENT",
    "BILLS_UTILITIES",
    "EMI",
    "SUBSCRIPTION",
    "EDUCATION",
    "RENT",
    "INSURANCE",
    "CASH_ATM",
    "INVESTMENT",
    "TRANSFER",
    "OTHER",
]


# ── raw source schemas ────────────────────────────────────────────────────────

class BankTransaction(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    timestamp: datetime
    amount: float                   # signed INR; positive=credit, negative=debit
    merchant_name: str
    channel: ChannelEnum = "BANK_TRANSFER"
    balance_after: float
    reference_id: str
    source_provenance: SourceProvenance = "bank_api"
    status: StatusEnum = "SUCCESS"


class UPITransaction(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    timestamp: datetime
    amount: float                   # signed INR
    direction: Literal["INBOUND", "OUTBOUND"]
    merchant_name: str
    txn_type: Literal["P2P", "P2M", "AUTOPAY"]
    status: Literal["SUCCESS", "FAILED_TECHNICAL", "FAILED_FUNDS"]
    upi_id: str
    source_provenance: SourceProvenance = "upi_api"


class SMSAlert(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    timestamp: datetime
    amount: float
    merchant_name: str
    alert_type: Literal["DEBIT_ALERT", "CREDIT_ALERT", "UPI_ALERT", "EMI_ALERT"]
    raw_text: str
    source_provenance: SourceProvenance = "sms_parser"


class EMISchedule(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    next_due_date: datetime
    amount: float                   # always positive
    schedule_type: Literal["EMI_LOAN", "SUBSCRIPTION", "INSURANCE", "RENT"]
    merchant_name: str
    recurrence_pattern: str         # e.g. "MONTHLY_5TH"
    remaining_tenure: int           # months
    status: Literal["ACTIVE", "PAID", "OVERDUE", "CANCELLED"]
    source_provenance: SourceProvenance = "emi_statement"


class OpenBankingFeed(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    timestamp: datetime
    amount: float
    merchant_name: str
    balance: float
    account_type: Literal["SAVINGS", "CURRENT", "LOAN", "CREDIT_CARD"]
    source_provenance: SourceProvenance = "open_banking_aa"


class VoiceTranscript(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    timestamp: datetime
    extracted_amount: float
    extracted_merchant: str
    extracted_type: Literal["EMI_PAYMENT", "BILL_PAYMENT", "OTHER"]
    confidence_score: float         # [0.0, 1.0]
    source_provenance: SourceProvenance = "voice_stt_parser"


class GSTInvoice(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    gstin: str
    timestamp: datetime
    taxable_value: float
    gst_amount: float
    buyer_gstin: str
    filing_status: Literal["ontime", "delayed", "missing"]
    filing_delay_days: int
    source_provenance: SourceProvenance = "gst_portal"


class EWayBill(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    gstin: str
    timestamp: datetime
    from_gstin: str
    to_gstin: str
    total_value: float
    main_hsn_code: str
    trans_distance: int
    source_provenance: SourceProvenance = "eway_bill_nic"


# ── canonical unified event (Tier 1 output / Tier 2 input) ───────────────────

class CanonicalEvent(BaseModel):
    """
    Unified financial event — every raw source normalises into this.
    Carries source_provenance so downstream tiers can trace origin.
    merchant_category and transaction_type are filled by Tier 2 classifier;
    ingestion layer leaves them as None.
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    timestamp: datetime
    amount: float                           # signed INR
    merchant_name: str
    channel: ChannelEnum = "OTHER"
    balance_after: Optional[float] = None
    reference_id: Optional[str] = None
    source_provenance: SourceProvenance = "bank_api"
    status: StatusEnum = "SUCCESS"
    recurrence_flag: bool = False
    anomaly_flag: bool = False

    # filled by Tier 2
    transaction_type: Optional[TransactionTypeEnum] = None
    merchant_category: Optional[MerchantCategoryEnum] = None
    classifier_confidence: Optional[float] = None
