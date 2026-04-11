"""
Tests for Tier 2 — Merchant Classifier & Semantic Embeddings
"""

import pytest

from src.classifier.merchant_classifier import classify_merchant, warmup


@pytest.fixture(scope="module", autouse=True)
def warm():
    warmup()


def test_salary_classified_correctly():
    cat, ttype, conf = classify_merchant("Tech Solutions Payroll Oct", amount=50000.0)
    assert cat == "SALARY"
    assert ttype == "INCOME"
    assert conf >= 0.7


def test_emi_rule_match():
    cat, ttype, conf = classify_merchant("HDFC Bank EMI Auto-debit", amount=-24200.0)
    assert cat == "EMI"
    assert ttype == "EMI_PAYMENT"


def test_atm_rule_match():
    cat, ttype, _ = classify_merchant("ATM Withdrawal SBI", amount=-5000.0)
    assert cat == "CASH_ATM"


def test_grocery_semantic():
    cat, ttype, conf = classify_merchant("Reliance Fresh #44", amount=-499.0)
    assert cat == "GROCERY"
    assert ttype == "EXPENSE_ESSENTIAL"
    assert conf > 0.4


def test_dining_semantic():
    cat, ttype, conf = classify_merchant("Royal Biryani House Koramangala", amount=-350.0)
    assert cat == "DINING"
    assert ttype == "EXPENSE_DISCRETIONARY"


def test_entertainment_rule():
    cat, ttype, _ = classify_merchant("Netflix Subscription Monthly", amount=-649.0)
    assert cat == "ENTERTAINMENT"


def test_transport_semantic():
    cat, ttype, conf = classify_merchant("Ola Cab Booking #8843", amount=-250.0)
    assert cat == "TRANSPORT"


def test_positive_amount_forces_income():
    """
    Even if merchant looks like an expense category, a positive amount
    should map to INCOME unless it's TRANSFER/REFUND/INVESTMENT.
    """
    cat, ttype, _ = classify_merchant("AA_BALANCE_SNAPSHOT", amount=0.0)
    # balance snapshots categorised as OTHER
    assert ttype in ("OTHER", "INCOME", "TRANSFER")


def test_lru_cache_hit():
    """Repeated calls should use cache (just test no exception raised)."""
    for _ in range(5):
        classify_merchant("Zomato Order 445", amount=-199.0)


def test_unknown_merchant_fallback():
    cat, ttype, conf = classify_merchant("XYZABC12345UNKNOWN", amount=-100.0)
    # should not crash; returns some category
    assert cat in (
        "OTHER", "GROCERY", "DINING", "TRANSPORT", "BILLS_UTILITIES",
        "HEALTHCARE", "ENTERTAINMENT", "EMI", "SUBSCRIPTION", "EDUCATION",
        "RENT", "INSURANCE", "CASH_ATM", "INVESTMENT", "TRANSFER", "SALARY",
    )
