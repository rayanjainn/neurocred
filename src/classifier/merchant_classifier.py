"""
Tier 2 — Merchant Category Classifier (all-MiniLM-L6-v2)

Implements the bi-encoder + semantic anchor methodology described in tier2.md:
  1. Pre-compute mean embeddings for each category from anchor phrases
  2. For each merchant string: encode → cosine similarity vs all anchors
  3. Assign highest-scoring category if score >= threshold (default 0.50)
  4. LRU cache for repeated merchant names (sub-microsecond on repeat)

Rule-based pre-filter (hybrid approach from math.md):
  High-confidence keywords bypass the model entirely for:
  SALARY, EMI, ATM patterns — avoids wasting compute on trivially classified strings.

Also assigns transaction_type from merchant_category via the mapping table.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

import numpy as np

from src.ingestion.schemas import MerchantCategoryEnum, TransactionTypeEnum

# ── lazy-import sentence_transformers to avoid import cost at module load ──────

_model = None
_anchor_vectors: dict[str, np.ndarray] = {}


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# ── category anchors (from tier2.md) ─────────────────────────────────────────

CATEGORY_ANCHORS: dict[str, list[str]] = {
    "SALARY": [
        "salary credit", "payroll disbursement", "monthly remuneration",
        "employer payment", "wage credit", "salary transfer", "income from employer",
        "monthly salary", "neft salary",
    ],
    "GROCERY": [
        "grocery store", "supermarket", "kirana shop", "daily groceries",
        "vegetables fruit market", "retail food store", "big basket", "dmart",
        "reliance fresh", "mother dairy",
    ],
    "DINING": [
        "restaurant food order", "cafe coffee", "zomato swiggy delivery",
        "biryani house", "pizza burger", "dining out", "food court",
        "quick service restaurant", "meal delivery",
    ],
    "TRANSPORT": [
        "cab taxi ride", "petrol fuel station", "bus metro ticket",
        "auto rickshaw", "ola uber travel", "fuel pump", "transportation",
        "rapido ride", "vehicle fuel",
    ],
    "BILLS_UTILITIES": [
        "electricity bill payment", "internet broadband", "mobile recharge",
        "utility payment", "water supply bill", "gas connection monthly",
        "telecom postpaid", "airtel jio bsnl",
    ],
    "HEALTHCARE": [
        "pharmacy medical store", "hospital clinic", "doctor consultation",
        "medicine prescription", "diagnostic lab test", "health checkup",
        "apollo max fortis", "1mg practo",
    ],
    "ENTERTAINMENT": [
        "movie cinema ticket", "streaming netflix hotstar", "bookMyShow",
        "event concert", "gaming entertainment", "amazon prime spotify",
        "pvr inox film",
    ],
    "EMI": [
        "loan emi payment", "installment debit", "bank loan repayment",
        "bajaj finance emi", "home loan emi", "car loan installment",
        "personal loan deduction", "emi auto-debit",
    ],
    "SUBSCRIPTION": [
        "monthly subscription service", "software saas plan",
        "professional membership", "recurring service fee",
        "adobe google workspace linkedin", "gym membership",
    ],
    "EDUCATION": [
        "school college tuition fee", "online course payment",
        "university fees", "coaching class", "byju udemy coursera",
        "education institute", "exam fee",
    ],
    "RENT": [
        "house rent payment", "flat apartment monthly rent",
        "pg accommodation", "maintenance housing society",
        "landlord rent transfer",
    ],
    "INSURANCE": [
        "insurance premium payment", "lic policy", "health insurance",
        "term life cover", "vehicle insurance renewal",
        "star health hdfc ergo",
    ],
    "CASH_ATM": [
        "atm cash withdrawal", "cash machine", "atm debit",
        "bank atm near", "cash withdrawal",
    ],
    "INVESTMENT": [
        "mutual fund sip", "stock market demat", "nsc ppf deposit",
        "investment portfolio", "zerodha groww investment",
        "savings bond fixed deposit",
    ],
    "TRANSFER": [
        "personal fund transfer", "send money friend family",
        "imps neft rtgs transfer", "p2p payment", "money transfer",
        "upi send receive",
    ],
    "OTHER": [
        "miscellaneous payment", "general transaction", "unknown merchant",
        "unclassified", "other expense",
    ],
}

# rule-based pre-filter patterns (case-insensitive)
RULE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(salary|payroll|remuneration|wage|pay\s*slip)\b", re.I), "SALARY"),
    (re.compile(r"\b(emi|equated monthly|loan\s+installment|home\s+loan|car\s+loan)\b", re.I), "EMI"),
    (re.compile(r"\b(atm|cash\s+withdrawal|cash\s+machine)\b", re.I), "CASH_ATM"),
    (re.compile(r"\b(sip|mutual\s+fund|demat|zerodha|groww|ppf|nsc)\b", re.I), "INVESTMENT"),
    (re.compile(r"\b(rent|landlord|pg\s+accommodation)\b", re.I), "RENT"),
    (re.compile(r"\b(netflix|hotstar|spotify|prime\s+video|youtube\s+premium)\b", re.I), "ENTERTAINMENT"),
    (re.compile(r"\b(pharmacy|medical|medicine|hospital|clinic|apollo|max\s+health|1mg|practo)\b", re.I), "HEALTHCARE"),
    (re.compile(r"\b(electricity|broadband|mobile\s+recharge|airtel|jio|bsnl|bescom|tata\s+power)\b", re.I), "BILLS_UTILITIES"),
    (re.compile(r"\b(petrol|diesel|fuel|hp\s+fuel|indian\s+oil|ola|uber|rapido|cab|taxi|auto\s+rickshaw)\b", re.I), "TRANSPORT"),
    (re.compile(r"\b(restaurant|cafe|zomato|swiggy|pizza|biryani|burger|coffee)\b", re.I), "DINING"),
    (re.compile(r"\b(grocery|kirana|dmart|reliance\s+fresh|big\s*basket|supermart|sabzi)\b", re.I), "GROCERY"),
    (re.compile(r"\b(insurance|lic|policy\s+premium|term\s+life)\b", re.I), "INSURANCE"),
    (re.compile(r"\b(college|school|tuition|byju|coursera|udemy|coaching)\b", re.I), "EDUCATION"),
    (re.compile(r"\baa_balance_snapshot\b", re.I), "OTHER"),
]

CATEGORY_TO_TYPE: dict[str, TransactionTypeEnum] = {
    "SALARY": "INCOME",
    "GROCERY": "EXPENSE_ESSENTIAL",
    "TRANSPORT": "EXPENSE_ESSENTIAL",
    "BILLS_UTILITIES": "EXPENSE_ESSENTIAL",
    "HEALTHCARE": "EXPENSE_ESSENTIAL",
    "RENT": "EXPENSE_ESSENTIAL",
    "INSURANCE": "EXPENSE_ESSENTIAL",
    "EDUCATION": "EXPENSE_DISCRETIONARY",
    "DINING": "EXPENSE_DISCRETIONARY",
    "ENTERTAINMENT": "EXPENSE_DISCRETIONARY",
    "CASH_ATM": "EXPENSE_DISCRETIONARY",
    "EMI": "EMI_PAYMENT",
    "SUBSCRIPTION": "SUBSCRIPTION",
    "INVESTMENT": "INVESTMENT",
    "TRANSFER": "TRANSFER",
    "OTHER": "OTHER",
}


def _build_anchor_vectors() -> None:
    """Pre-compute mean embeddings for each category anchor set."""
    global _anchor_vectors
    if _anchor_vectors:
        return
    model = _get_model()
    for category, phrases in CATEGORY_ANCHORS.items():
        vecs = model.encode(phrases, normalize_embeddings=True)
        _anchor_vectors[category] = np.mean(vecs, axis=0)
        # re-normalise the mean vector
        norm = np.linalg.norm(_anchor_vectors[category])
        if norm > 0:
            _anchor_vectors[category] /= norm


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # both are already normalised


def _rule_classify(merchant: str) -> Optional[str]:
    """Return category from rule-based patterns if high-confidence match."""
    for pattern, category in RULE_PATTERNS:
        if pattern.search(merchant):
            return category
    return None


@lru_cache(maxsize=4096)
def _embed_merchant(merchant: str) -> "np.ndarray":
    model = _get_model()
    vec = model.encode([merchant], normalize_embeddings=True)[0]
    return vec


def classify_merchant(
    merchant_name: str,
    amount: float = 0.0,
    threshold: float = 0.50,
) -> tuple[MerchantCategoryEnum, TransactionTypeEnum, float]:
    """
    Classify a merchant string into (merchant_category, transaction_type, confidence).

    Pipeline (from tier2.md):
      1. Rule-based pre-filter (high-confidence keywords)
      2. LRU cache lookup
      3. MiniLM embedding + cosine similarity vs anchor vectors
      4. Amount-sign override: positive amounts with no INCOME category → INCOME

    Returns:
        merchant_category: MerchantCategoryEnum
        transaction_type: TransactionTypeEnum
        confidence: float [0.0, 1.0]
    """
    # ensure anchors are built (lazy, once)
    if not _anchor_vectors:
        _build_anchor_vectors()

    # rule pre-filter
    rule_cat = _rule_classify(merchant_name)
    if rule_cat:
        t_type = CATEGORY_TO_TYPE.get(rule_cat, "OTHER")
        # amount sign override: if amount > 0 and type isn't INCOME → set INCOME
        if amount > 0 and t_type not in ("INCOME", "TRANSFER", "REFUND", "INVESTMENT"):
            t_type = "INCOME"
        return rule_cat, t_type, 1.0  # type: ignore[return-value]

    # embedding path
    vec = _embed_merchant(merchant_name.strip().lower())
    best_cat = "OTHER"
    best_score = -1.0
    for cat, anchor_vec in _anchor_vectors.items():
        score = _cosine_similarity(vec, anchor_vec)
        if score > best_score:
            best_score = score
            best_cat = cat

    if best_score < threshold:
        best_cat = "OTHER"
        best_score = threshold  # use threshold as min confidence

    t_type = CATEGORY_TO_TYPE.get(best_cat, "OTHER")
    if amount > 0 and t_type not in ("INCOME", "TRANSFER", "REFUND", "INVESTMENT"):
        t_type = "INCOME"

    return best_cat, t_type, round(best_score, 4)  # type: ignore[return-value]


def warmup() -> None:
    """Pre-build anchor vectors and warm the LRU cache with common merchants."""
    _build_anchor_vectors()
    common = [
        "Salary from Employer",
        "Zomato Order",
        "HDFC EMI",
        "Airtel Postpaid",
        "ATM Withdrawal",
        "Netflix Subscription",
        "Reliance Fresh",
    ]
    for m in common:
        classify_merchant(m)
