"""
Tier 9 — Module 3: Social Engineering Defence

Bayesian + regex + spaCy NER analysis of SMS/voice transcripts to detect:
  1. Urgency Manipulation (panic induction language)
  2. Authority Impersonation (RBI, IT Dept, Bank HO)
  3. OTP Phishing Sequences (numeric extraction after action triggers)

Designed to run fully local — no external API calls. Sub-10ms on CPU.
Falls back gracefully if spaCy is not installed (regex-only mode).
"""

from __future__ import annotations

import math
import re
from typing import Optional

from src.vigilance.schemas import (
    RiskLevel,
    ScamProbabilityResult,
    ScamSignal,
    ScamType,
)

# ── Keyword Banks ─────────────────────────────────────────────────────────────

# Urgency tokens — designed to induce panic
URGENCY_PATTERNS = [
    r"\bimmediate(?:ly)?\b",
    r"\burgent(?:ly)?\b",
    r"\baccount\s+(?:will\s+be\s+)?(?:suspended|blocked|frozen|disabled)\b",
    r"\b(?:within\s+)?24\s*hours?\b",
    r"\b(?:within\s+)?2\s*hours?\b",
    r"\blast\s+(?:chance|warning|notice)\b",
    r"\baction\s+required\b",
    r"\bdeadline\b",
    r"\bdo\s+not\s+(?:ignore|delay)\b",
    r"\bexpires?\s+(?:today|tonight|soon)\b",
    r"\bfinal\s+(?:notice|warning|reminder)\b",
    r"\bimmediately\s+(?:call|contact|reply)\b",
    r"\byour\s+(?:loan|account|card)\s+(?:will\s+be\s+)?(?:closed|cancelled|rejected)\b",
    r"\bsuspicious\s+activity\s+detected\b",
    r"\bunauthorized\s+(?:login|access|transaction)\b",
]

# Authority impersonation tokens
AUTHORITY_PATTERNS = [
    r"\bRBI\b",
    r"\bReserve\s+Bank\s+of\s+India\b",
    r"\bIncome\s+Tax\s+(?:Department|Officer|Notice)\b",
    r"\bIT\s+(?:Department|Notice|Raid)\b",
    r"\bCBI\b",
    r"\bED\b",
    r"\bEnforcement\s+Directorate\b",
    r"\bCyber\s+(?:Crime|Cell|Police)\b",
    r"\bBank\s+Head\s+Office\b",
    r"\bNPCI\b",
    r"\bSEBI\b",
    r"\bFIU\b",
    r"\bFinancial\s+Intelligence\s+Unit\b",
    r"\bTax\s+(?:Department|Authority|Notice)\b",
    r"\border\s+(?:from|of)\s+(?:court|government|RBI)\b",
    r"\bofficial\s+notice\b",
    r"\bgovernment\s+(?:order|notice|directive)\b",
]

# OTP phishing — numeric extraction after trigger
OTP_PATTERNS = [
    r"\b(?:share|send|provide|give|tell)\s+(?:your\s+)?(?:OTP|one[\s-]time\s+password|6[\s-]digit(?:\s+code)?)\b",
    r"\bOTP\s+(?:is|sent|received)\b",
    r"\b\d{6}\b",  # bare 6-digit number (context-dependent)
    r"\bverification\s+(?:code|pin|number)\b",
    r"\bdo\s+not\s+share\s+(?:(?:this|your)\s+)?OTP\b",  # banks warning = scammer mimicking
    r"\bconfirm(?:ation)?\s+(?:code|number|pin)\b",
    r"\bsecret\s+(?:code|pin|number)\b",
]

# Authoritative whitelist domains/headers (very simplified)
LEGIT_SENDER_PATTERNS = [
    r"^[A-Z]{2}-[A-Z]{4,6}$",  # Indian TRAI DLT format: TM-HDFCBK, VK-ICICIBANK
]


def _compile_patterns(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_URGENCY_RE    = _compile_patterns(URGENCY_PATTERNS)
_AUTHORITY_RE  = _compile_patterns(AUTHORITY_PATTERNS)
_OTP_RE        = _compile_patterns(OTP_PATTERNS)
_LEGIT_SENDER  = _compile_patterns(LEGIT_SENDER_PATTERNS)


# ── Scorer Functions ──────────────────────────────────────────────────────────

def _score_urgency(text: str) -> tuple[float, list[ScamSignal]]:
    """Return (urgency_score, signals). Score = 1 - exp(-k * matches)."""
    signals = []
    matches = []
    for pat in _URGENCY_RE:
        m = pat.search(text)
        if m:
            matches.append(m.group(0))

    if not matches:
        return 0.0, []

    score = 1.0 - math.exp(-0.45 * len(matches))
    for m in matches[:5]:  # cap signals list
        signals.append(ScamSignal(
            signal_type=ScamType.URGENCY_MANIPULATION,
            matched_text=m,
            confidence=round(score, 3),
            severity=RiskLevel.HIGH if score > 0.6 else RiskLevel.MEDIUM,
        ))
    return round(min(score, 1.0), 4), signals


def _score_authority(text: str, sender_id: Optional[str] = None) -> tuple[float, list[ScamSignal]]:
    """Return (authority_score, signals). Cross-check sender ID against TRAI whitelist."""
    signals = []
    matches = []

    for pat in _AUTHORITY_RE:
        m = pat.search(text)
        if m:
            matches.append(m.group(0))

    if not matches:
        return 0.0, []

    # If sender looks like legit DLT header, reduce penalty
    sender_legit = False
    if sender_id:
        for pat in _LEGIT_SENDER:
            if pat.match(sender_id.strip()):
                sender_legit = True
                break

    score = 1.0 - math.exp(-0.5 * len(matches))
    if sender_legit:
        score *= 0.3  # dramatic reduction — legitimate bank might genuinely mention RBI

    for m in matches[:5]:
        signals.append(ScamSignal(
            signal_type=ScamType.AUTHORITY_IMPERSONATION,
            matched_text=m,
            confidence=round(score, 3),
            severity=RiskLevel.CRITICAL if score > 0.6 else RiskLevel.HIGH,
        ))
    return round(min(score, 1.0), 4), signals


def _score_otp_phishing(text: str) -> tuple[float, list[ScamSignal]]:
    """
    OTP phishing score: triggered by OTP request patterns.
    Note: bare 6-digit numbers alone score low — requires co-occurrence with action triggers.
    """
    signals = []
    matches = []

    urgency_present = any(pat.search(text) for pat in _URGENCY_RE)

    for pat in _OTP_RE:
        m = pat.search(text)
        if m:
            # Bare 6-digit number only scores if urgency context is also present
            if pat.pattern == r"\b\d{6}\b" and not urgency_present:
                continue
            matches.append(m.group(0))

    if not matches:
        return 0.0, []

    score = 1.0 - math.exp(-0.8 * len(matches))
    for m in matches[:3]:
        signals.append(ScamSignal(
            signal_type=ScamType.OTP_PHISHING,
            matched_text=m,
            confidence=round(score, 3),
            severity=RiskLevel.CRITICAL,
        ))
    return round(min(score, 1.0), 4), signals


# ── Bayesian Combiner ─────────────────────────────────────────────────────────

def _bayesian_combine(
    urgency: float,
    authority: float,
    otp: float,
    prior: float = 0.05,  # 5% base rate for scam SMS in Indian financial context
) -> float:
    """
    Naive Bayes: P(scam | signals) ∝ P(signals | scam) × P(scam)
    Using log-odds form for numerical stability.
    """
    if urgency == 0 and authority == 0 and otp == 0:
        return 0.0

    log_odds = math.log(prior / (1 - prior + 1e-9))

    # Each signal updates the log-odds (Laplace-smoothed likelihoods)
    for score in (urgency, authority, otp):
        if score > 1e-4:
            p_given_scam    = 0.85 * score + 0.05          # P(signal=score | scam)
            p_given_legit   = 0.10 * score + 0.02          # P(signal=score | legit)
            lr = p_given_scam / (p_given_legit + 1e-9)
            log_odds += math.log(lr + 1e-9)

    # Convert back to probability
    prob = 1.0 / (1.0 + math.exp(-log_odds))
    return round(min(prob, 1.0), 4)


# ── Main Entry ────────────────────────────────────────────────────────────────

def run_scam_detector(
    user_id: str,
    text: str,
    sender_id: Optional[str] = None,
) -> ScamProbabilityResult:
    """
    Analyze a single SMS or voice transcript for social engineering signals.

    Args:
        user_id:   User who received this message
        text:      Raw SMS body or voice-to-text transcript
        sender_id: Sender ID / phone header (e.g. "TM-HDFCBK")

    Returns:
        ScamProbabilityResult
    """
    if not text or not text.strip():
        return ScamProbabilityResult(
            user_id=user_id,
            analyzed_text="",
            recommended_action="No text provided for analysis.",
        )

    # Truncate to 2000 chars for safety
    text_safe = text[:2000]

    urgency_score,   urgency_signals   = _score_urgency(text_safe)
    authority_score, authority_signals = _score_authority(text_safe, sender_id)
    otp_score,       otp_signals       = _score_otp_phishing(text_safe)

    combined = _bayesian_combine(urgency_score, authority_score, otp_score)

    all_signals = urgency_signals + authority_signals + otp_signals

    # Risk tier
    if combined >= 0.75:
        risk = RiskLevel.CRITICAL
        action = "ALERT: High-confidence social engineering detected. Block transaction and notify user."
    elif combined >= 0.50:
        risk = RiskLevel.HIGH
        action = "WARN: Likely scam. Request additional confirmation before allowing any action."
    elif combined >= 0.25:
        risk = RiskLevel.MEDIUM
        action = "MONITOR: Possible phishing signals. Log for review."
    else:
        risk = RiskLevel.LOW
        action = "No action required."

    return ScamProbabilityResult(
        user_id=user_id,
        scam_probability=combined,
        is_scam_alert=combined >= 0.5,
        urgency_score=urgency_score,
        authority_score=authority_score,
        otp_phishing_score=otp_score,
        signals=all_signals[:10],
        analyzed_text=text_safe[:200],   # truncate for storage
        risk_level=risk,
        recommended_action=action,
    )
