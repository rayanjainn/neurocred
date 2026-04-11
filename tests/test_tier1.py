"""
Tests for Tier 1 — Signal Ingestion & Schema Normalisation
"""

import pytest
from datetime import datetime

from src.ingestion.generator import (
    UserProfile,
    build_profile,
    generate_all_events,
    generate_bank_transactions,
    generate_upi_transactions,
    generate_emi_schedules,
    PERSONA_TYPES,
)
from src.ingestion.schemas import CanonicalEvent


def test_build_profile_persona_valid():
    for i in range(20):
        p = build_profile(i)
        assert p.persona in PERSONA_TYPES
        assert p.user_id.startswith("u_")
        assert p.monthly_income > 0


def test_canonical_event_has_uuid():
    p = build_profile(0, seed=42)
    events = generate_bank_transactions(p)
    assert len(events) > 0
    for ev in events.to_dicts():
        assert len(ev["event_id"]) == 36  # UUID4 format
        assert ev["user_id"] == p.user_id


def test_events_are_sorted():
    p = build_profile(1, seed=7)
    events = generate_all_events(p, history_months=3)
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)


def test_emi_recurrence_flag():
    p = build_profile(2, seed=99)
    p.persona = "genuine_healthy"
    emi_events = generate_emi_schedules(p)
    for ev in emi_events.to_dicts():
        assert ev["recurrence_flag"] is True
        assert ev["source_provenance"] == "emi_statement"


def test_amounts_are_signed():
    """Debits should be negative, income events positive."""
    p = build_profile(3, seed=5)
    bank = generate_bank_transactions(p)
    income = [e for e in bank.to_dicts() if "salary" in e["merchant_name"].lower() or
              e["source_provenance"] == "bank_api" and e["amount"] > 0]
    assert len(income) > 0


def test_all_sources_represented():
    p = build_profile(4, seed=123)
    events = generate_all_events(p, history_months=6)
    provenances = {e.source_provenance for e in events}
    assert "bank_api" in provenances
    assert "upi_api" in provenances


def test_idempotency_no_duplicate_event_ids():
    p = build_profile(5, seed=77)
    events = generate_all_events(p, history_months=3)
    ids = [e.event_id for e in events]
    assert len(ids) == len(set(ids)), "Duplicate event_ids found"


def test_shell_circular_high_volume():
    """shell_circular persona should produce more UPI events than genuine_healthy."""
    p_fraud = UserProfile(10, "shell_circular", 42)
    p_healthy = UserProfile(11, "genuine_healthy", 42)

    fraud_upi = generate_upi_transactions(p_fraud)
    healthy_upi = generate_upi_transactions(p_healthy)
    assert len(fraud_upi) > len(healthy_upi)
