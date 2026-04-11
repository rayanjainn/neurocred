"""
Tier 1 — Synthetic Financial Signal Generator
Phase 1 of the pipeline: writes chunked Parquet files to data/raw/

Exact same toolchain as CreditIQ:
  - Faker (en_IN) for merchant/bank names
  - SDV GaussianCopulaSynthesizer for cross-field correlated profile synthesis
  - numpy lognormal for amounts (μ/σ per persona)
  - Exponential inter-arrivals (Poisson-like) for genuine; Gaussian burst for fraud
  - Polars DataFrames; Parquet chunks (10 000 rows each) → data/raw/

5 personas, weights: genuine_healthy 40%, genuine_struggling 25%,
shell_circular 15%, paper_trader 10%, new_to_credit 10%

Run as:  python -m src.ingestion.generator
Outputs:
  data/raw/bank_transactions_chunk_NNNN.parquet
  data/raw/upi_transactions_chunk_NNNN.parquet
  data/raw/sms_alerts_chunk_NNNN.parquet
  data/raw/emi_schedules_chunk_NNNN.parquet
  data/raw/open_banking_chunk_NNNN.parquet
  data/raw/voice_transcripts_chunk_NNNN.parquet
  data/raw/user_profiles.parquet
"""

from __future__ import annotations

import hashlib
import math
import random
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import polars as pl
from faker import Faker
from tqdm import tqdm
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme
import logging

# ── logging setup ─────────────────────────────────────────────────────────────

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "simulation": "magenta",
})

console = Console(theme=custom_theme)
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("airavat.generator")

# ── constants ─────────────────────────────────────────────────────────────────

PERSONA_TYPES: list[str] = [
    "genuine_healthy",
    "genuine_struggling",
    "shell_circular",
    "paper_trader",
    "new_to_credit",
]

N_PROFILES: int = 100
CHUNK_SIZE: int = 10_000
RAW_DATA_PATH: Path = Path("data/raw")
REFERENCE_DATE: datetime = datetime(2026, 4, 11)

PROFILE_TYPES: list[str] = [p.upper() for p in PERSONA_TYPES]
PROFILE_WEIGHTS: list[float] = [0.40, 0.25, 0.15, 0.10, 0.10]

BANK_HANDLES: list[str] = ["okaxis", "okhdfcbank", "okicici", "oksbi", "ybl", "ibl", "paytm"]

# Merchant templates — intentionally noisy to force MiniLM usage in Tier 2
MERCHANT_TEMPLATES: dict[str, list[str]] = {
    "SALARY": [
        "Tech Solutions Payroll Oct", "Monthly Remuneration Trans",
        "Infosys Ltd Salary", "NEFT-HDFC-Employer-Cr",
        "Payroll Disbursement Q3", "Wipro Salary Credit",
        "Tata Consultancy Wages", "HCL Technologies Pay",
    ],
    "GROCERY": [
        "Reliance Fresh #44", "Mother Dairy Store",
        "Green Grocery Kirana", "DMart Retail Pvt Ltd",
        "Big Basket Order 99X", "Local Sabzi Mandi",
        "Spencers Supermart", "More Megastore",
        "Star Bazaar", "Nilgiris Fresh",
    ],
    "DINING": [
        "Blue Tokai Coffee Gurgaon", "Royal Biryani House",
        "Zomato-Order-992", "Swiggy Restro Deliv",
        "Dominos Pizza Outlet 12", "Chai Point Cafe",
        "McDonalds Drive Thru", "Burger King BLR",
        "KFC Outlet HSR Layout", "Barbeque Nation",
    ],
    "TRANSPORT": [
        "Ola Cab Booking", "Uber Technologies India",
        "BMTC Monthly Pass", "Indian Oil Petrol Pump",
        "Rapido Ride 87", "Metro Rail Recharge",
        "HP Fuel Station", "BPCL Pump Station",
        "Namma Metro Card Top-up", "IndiGo Flight Booking",
    ],
    "BILLS_UTILITIES": [
        "BSNL Broadband Bill", "Airtel Postpaid Recharge",
        "BESCOM Electricity Bill", "Tata Power Monthly",
        "Jio Recharge 599", "BWSSB Water Supply",
        "Gas Agency Monthly", "Mahanagar Gas",
        "MTNL Bill Payment", "Hathway Internet",
    ],
    "HEALTHCARE": [
        "Apollo Pharmacy #32", "Max Healthcare OPD",
        "Practo Consultation Fee", "1mg Medicine Order",
        "Fortis Lab Test", "Generic Medical Store",
        "Medplus Pharmacy", "Netmeds Order",
        "Narayana Health Consult", "Thyrocare Lab",
    ],
    "ENTERTAINMENT": [
        "Netflix Subscription", "BookMyShow Tickets",
        "Hotstar Premium Renewal", "Amazon Prime Video",
        "Spotify Premium Monthly", "PVR Cinemas Booking",
        "SonyLIV Plan", "Zee5 Subscription",
        "INOX Movie Tickets", "Lionsgate Play",
    ],
    "EMI": [
        "HDFC Bank EMI Auto-debit", "Bajaj Finance EMI",
        "ICICI Home Loan EMI", "Kotak Personal Loan",
        "Axis Bank Car Loan", "SBI EMI Collection",
        "Tata Capital EMI", "Fullerton India EMI",
        "Piramal Finance EMI", "L&T Finance EMI",
    ],
    "SUBSCRIPTION": [
        "Adobe CC Subscription", "Zoho CRM Monthly",
        "Google Workspace Plan", "LinkedIn Premium",
        "AWS Cloud Services", "Gym Membership Monthly",
        "Microsoft 365 Plan", "Notion Premium",
        "Canva Pro Monthly", "Freshdesk Plan",
    ],
    "EDUCATION": [
        "Coursera Subscription", "BYJU's Fee Payment",
        "College Tuition Fee", "Udemy Course Purchase",
        "School Fee Online", "Unacademy Plus",
        "Vedantu Classes", "IIT JEE Coaching",
        "Khan Academy Plus", "Coding Ninjas",
    ],
    "RENT": [
        "Rent Payment Landlord", "Housing Society Maintenance",
        "PG Accommodation Monthly", "Flat Rent Transfer",
        "NestAway Rent", "Housing.com Rent",
    ],
    "INSURANCE": [
        "LIC Premium Debit", "Star Health Premium",
        "HDFC Ergo Policy Renewal", "Term Life Insurance",
        "Bajaj Allianz Premium", "ICICI Lombard Policy",
    ],
    "CASH_ATM": [
        "ATM Withdrawal SBI", "HDFC ATM Cash",
        "ICICI ATM Near Metro", "ATM-AXIS-INR",
        "Kotak ATM Withdrawal", "Yes Bank ATM",
    ],
    "INVESTMENT": [
        "Zerodha Demat Cr", "Groww Mutual Fund SIP",
        "HDFC Mutual Fund", "PPF Deposit",
        "NSC Investment", "LIC Premium Annual",
        "ELSS Tax Saving", "Kuvera MF",
    ],
    "TRANSFER": [
        "NEFT Transfer Personal", "IMPS To Friend",
        "UPI P2P Send", "Family Remittance",
        "Self Account Transfer", "RTGS Payment",
    ],
}

CATEGORY_TO_TYPE: dict[str, str] = {
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


# ── MSME constants

STATE_CODES = [6, 7, 8, 9, 19, 22, 24, 27, 29, 33, 36]
DOC_TYPES = ["INV", "INV", "INV", "CHL", "BIL"]
VEHICLE_PREFIXES = ["KA", "MH", "DL", "TN", "GJ", "RJ", "UP", "WB"]
HSN_SECTORS = {
    "iron_steel": ["7201", "7202", "7204", "7207", "7208", "7209", "7210", "7213"],
    "textiles": ["5208", "5209", "5210", "5211", "6001", "6002", "6006", "5201"],
    "food_grains": ["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008"],
    "chemicals": ["2801", "2802", "2803", "2804", "2901", "2902", "3801", "3802"],
    "machinery": ["8401", "8402", "8403", "8404", "8405", "8406", "8407", "8408"],
    "electronics": ["8501", "8502", "8503", "8504", "8505", "8506", "8507", "8508"],
    "plastics": ["3901", "3902", "3903", "3904", "3905", "3906", "3907", "3908"],
    "paper": ["4801", "4802", "4803", "4804", "4805", "4701", "4702", "4703"],
}
HSN_PRODUCT_MAP = {
    "7201": "pig iron",
    "7202": "ferro alloys",
    "7204": "ferrous scrap",
    "7207": "semi-finished steel",
    "7208": "flat-rolled steel",
    "7209": "cold-rolled steel",
    "7210": "coated steel",
    "7213": "steel wire rod",
    "5208": "woven cotton fabric",
    "5209": "heavy cotton fabric",
    "5210": "mixed cotton fabric",
    "5211": "denim fabric",
    "6001": "pile fabric",
    "6002": "knitted fabric",
    "6006": "technical fabric",
    "5201": "raw cotton",
    "1001": "wheat",
    "1002": "rye",
    "1003": "barley",
    "1004": "oats",
    "1005": "maize",
    "1006": "rice",
    "1007": "sorghum",
    "1008": "buckwheat",
    "2801": "fluorine chlorine",
    "2802": "sulphur",
    "2803": "carbon black",
    "2804": "hydrogen",
    "2901": "acyclic hydrocarbons",
    "2902": "cyclic hydrocarbons",
    "3801": "artificial graphite",
    "3802": "activated carbon",
    "8401": "nuclear reactor parts",
    "8402": "steam boilers",
    "8403": "heating boilers",
    "8404": "auxiliary plant",
    "8405": "gas generators",
    "8406": "steam turbines",
    "8407": "spark ignition engines",
    "8408": "compression engines",
    "8501": "electric motors",
    "8502": "generators",
    "8503": "motor parts",
    "8504": "transformers",
    "8505": "electromagnets",
    "8506": "primary cells",
    "8507": "batteries",
    "8508": "vacuum cleaners",
    "3901": "polyethylene",
    "3902": "polypropylene",
    "3903": "polystyrene",
    "3904": "pvc resin",
    "3905": "polyvinyl acetate",
    "3906": "acrylic polymers",
    "3907": "polyacetals",
    "3908": "polyamides",
    "4801": "newsprint",
    "4802": "writing paper",
    "4803": "tissue paper",
    "4804": "kraft paper",
    "4805": "other paper",
    "4701": "mechanical pulp",
    "4702": "chemical pulp",
    "4703": "kraft pulp",
}

# ── helpers ───────────────────────────────────────────────────────────────────
# --- MSME Generation Functions from CreditIQ ---

def generate_gstin(state_code: int, fake: Faker) -> str:
    """
    generates validformat gstin given state code
    pan portion follows 5letter 4digit 1letter pattern
    """
    pan_letters_a = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
    pan_digits = "".join(random.choices("0123456789", k=4))
    pan_letter_b = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    pan_like = pan_letters_a + pan_digits + pan_letter_b
    entity = str(random.randint(1, 9))
    checksum = str(random.randint(0, 9))
    return f"{state_code:02d}{pan_like}{entity}Z{checksum}"

def generate_vehicle_no(fake: Faker) -> str:
    """
    generates synthetic indian vehicle registration number
    """
    prefix = random.choice(VEHICLE_PREFIXES)
    district = f"{random.randint(10, 99)}"
    series = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2))
    number = f"{random.randint(1000, 9999)}"
    return f"{prefix}{district}{series}{number}"



def get_active_period(profile: dict) -> tuple[datetime, datetime]:
    """
    returns start end datetimes profile based business age
    """
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=profile["age_months"] * 30)
    return start_dt, end_dt

def generate_gst_invoices(profiles: list[dict], fake: Faker) -> pl.DataFrame:
    """
    generates gst invoice records profiles returns single polars dataframe
    invoice counts taxable values filing behaviour vary profile type
    """
    all_gstins = [p["gstin"] for p in profiles]

    n_invoice_map: dict[str, tuple[int, int]] = {
        "GENUINE_HEALTHY": (2, 5),
        "GENUINE_STRUGGLING": (1, 3),
        "SHELL_CIRCULAR": (3, 6),
        "PAPER_TRADER": (4, 8),
        "NEW_TO_CREDIT": (1, 8),
    }

    lognormal_params: dict[str, tuple[float, float]] = {
        "GENUINE_HEALTHY": (10.8, 0.8),
        "GENUINE_STRUGGLING": (9.9, 1.2),
        "SHELL_CIRCULAR": (12.2, 0.4),
        "PAPER_TRADER": (12.6, 0.3),
        "NEW_TO_CREDIT": (9.6, 1.5),
    }

    filing_weights: dict[str, list[float]] = {
        "GENUINE_HEALTHY": [0.85, 0.12, 0.03],
        "GENUINE_STRUGGLING": [0.55, 0.35, 0.10],
        "SHELL_CIRCULAR": [0.70, 0.28, 0.02],
        "PAPER_TRADER": [0.60, 0.30, 0.10],
        "NEW_TO_CREDIT": [0.75, 0.20, 0.05],
    }

    records: list[dict] = []

    print("generating gst invoices for genuine healthy profiles")
    for profile in profiles:
        ptype = profile["profile_type"]
        age = profile["age_months"]

        if ptype == "NEW_TO_CREDIT":
            n_invoices = random.randint(1, 8)
        else:
            lo, hi = n_invoice_map[ptype]
            n_invoices = age * random.randint(lo, hi)

        start_dt, end_dt = _get_active_period(profile["age_months"])
        timestamps = _sample_timestamps(start_dt, end_dt, n_invoices, burst=False)

        mean, sigma = lognormal_params[ptype]
        weights = filing_weights[ptype]

        for ts in timestamps:
            taxable_value = float(np.random.lognormal(mean=mean, sigma=sigma))
            gst_amount = taxable_value * 0.18

            if random.random() < 0.30:
                buyer_gstin = "URP"
            else:
                other_gstins = [g for g in all_gstins if g != profile["gstin"]]
                buyer_gstin = random.choice(other_gstins) if other_gstins else "URP"

            filing_status = random.choices(
                ["ontime", "delayed", "missing"], weights=weights
            )[0]

            if filing_status == "ontime":
                filing_delay_days = 0
            elif filing_status == "delayed":
                filing_delay_days = int(np.random.exponential(scale=12))
            else:
                filing_delay_days = int(np.random.exponential(scale=30))

            records.append({
                "user_id": profile["user_id"],
                "gstin": profile["gstin"],
                "invoice_id": f"INV{int(ts.timestamp() * 1000)}",
                "timestamp": ts.isoformat(),
                "taxable_value": round(taxable_value, 2),
                "gst_amount": round(gst_amount, 2),
                "buyer_gstin": buyer_gstin,
                "filing_status": filing_status,
                "filing_delay_days": filing_delay_days,
                "synthetic_batch_id": "batch_001",
            })

    return pl.DataFrame(records)

def generate_eway_bills(profiles: list[dict], fake: Faker) -> pl.DataFrame:
    """
    generates eway bill records official field structure
    paper traders produce bills low distance mixed hsn codes
    shell companies produce bills reflecting minimal physical goods movement
    """
    all_gstins = [p["gstin"] for p in profiles]
    gstin_to_state: dict[str, int] = {p["gstin"]: p["state_code"] for p in profiles}
    gstin_to_name: dict[str, str] = {p["gstin"]: p["business_name"] for p in profiles}

    all_sector_keys = list(HSN_SECTORS.keys())

    records: list[dict] = []

    print("generating eway bills for all profiles")
    for profile in profiles:
        ptype = profile["profile_type"]
        age = profile["age_months"]

        if ptype == "GENUINE_HEALTHY":
            n_bills = age * random.randint(2, 6)
        elif ptype == "GENUINE_STRUGGLING":
            n_bills = age * random.randint(1, 3)
        elif ptype == "SHELL_CIRCULAR":
            n_bills = age * random.randint(0, 2)
        elif ptype == "PAPER_TRADER":
            n_bills = age * random.randint(5, 10)
        else:
            n_bills = random.randint(0, 5)

        if n_bills == 0:
            continue

        start_dt, end_dt = _get_active_period(profile["age_months"])
        timestamps = _sample_timestamps(start_dt, end_dt, n_bills, burst=False)

        if ptype == "GENUINE_HEALTHY":
            txbl_mean, txbl_sigma = 10.5, 0.8
        elif ptype == "PAPER_TRADER":
            txbl_mean, txbl_sigma = 12.5, 0.3
        else:
            txbl_mean, txbl_sigma = 10.0, 1.0

        for ts in timestamps:
            if ptype == "PAPER_TRADER":
                if random.random() < 0.60:
                    eligible = [s for s in all_sector_keys if s != profile["hsn_sector"]]
                    chosen_sector = random.choice(eligible) if eligible else profile["hsn_sector"]
                else:
                    chosen_sector = profile["hsn_sector"]
            else:
                if random.random() < 0.10:
                    chosen_sector = random.choice(all_sector_keys)
                else:
                    chosen_sector = profile["hsn_sector"]

            hsn_code = random.choice(HSN_SECTORS[chosen_sector])
            product_name = HSN_PRODUCT_MAP.get(hsn_code, "goods")

            if random.random() < 0.20:
                to_gstin = "URP"
                to_trd_name = "unregistered person"
                to_state_code = profile["state_code"]
            else:
                other_gstins = [g for g in all_gstins if g != profile["gstin"]]
                to_gstin = random.choice(other_gstins) if other_gstins else "URP"
                to_trd_name = gstin_to_name.get(to_gstin, "buyer")
                to_state_code = gstin_to_state.get(to_gstin, profile["state_code"])

            intra_state = profile["state_code"] == to_state_code

            trans_mode = random.choices([1, 2, 3, 4], weights=[0.70, 0.20, 0.05, 0.05])[0]

            if ptype == "PAPER_TRADER":
                trans_distance = random.randint(1, 5)
            else:
                trans_distance = random.randint(50, 2000)

            taxable_amount = float(np.random.lognormal(mean=txbl_mean, sigma=txbl_sigma))

            cgst_value = round(taxable_amount * 0.09, 2) if intra_state else 0.0
            sgst_value = round(taxable_amount * 0.09, 2) if intra_state else 0.0
            igst_value = 0.0 if intra_state else round(taxable_amount * 0.18, 2)
            cess_value = 0.0
            oth_value = 0.0
            tot_inv_value = round(taxable_amount + cgst_value + sgst_value + igst_value, 2)

            records.append({
                "user_id": profile["user_id"],
                "gstin": profile["gstin"],
                "eway_id": f"EWB{int(ts.timestamp())}",
                "timestamp": ts.isoformat(),
                "userGstin": profile["gstin"],
                "supplyType": random.choices(["O", "I"], weights=[0.8, 0.2])[0],
                "subSupplyType": random.choices([1, 4, 9, 1], weights=[0.7, 0.1, 0.1, 0.1])[0],
                "subSupplyDesc": "",
                "docType": random.choice(DOC_TYPES),
                "docNo": fake.bothify(text="???###??##"),
                "docDate": ts.strftime("%d/%m/%Y"),
                "transType": random.choices([1, 2], weights=[0.8, 0.2])[0],
                "fromGstin": profile["gstin"],
                "fromTrdName": profile["business_name"],
                "fromAddr1": fake.street_address()[:120],
                "fromAddr2": "",
                "fromPlace": fake.city()[:50],
                "fromPincode": random.randint(100000, 999999),
                "fromStateCode": profile["state_code"],
                "actualFromStateCode": profile["state_code"],
                "toGstin": to_gstin,
                "toTrdName": to_trd_name,
                "toAddr1": fake.street_address()[:120],
                "toAddr2": "",
                "toPlace": fake.city()[:50],
                "toPincode": random.randint(100000, 999999),
                "toStateCode": to_state_code,
                "actualToStateCode": to_state_code,
                "transMode": trans_mode,
                "transDistance": trans_distance,
                "transporterName": fake.company()[:25] if trans_mode in [2, 3, 4] else "",
                "transporterId": "",
                "transDocNo": fake.bothify(text="TRN#####") if trans_mode in [2, 3] else "",
                "transDocDate": ts.strftime("%d/%m/%Y") if trans_mode in [2, 3] else "",
                "vehicleNo": generate_vehicle_no(fake) if trans_mode == 1 else "",
                "vehicle_type": "R",
                "main_hsn_code": hsn_code,
                "tot_inv_value": tot_inv_value,
                "itemList_itemNo": 1,
                "itemList_hsnCode": hsn_code,
                "itemList_productName": product_name,
                "itemList_productDesc": product_name,
                "itemList_quantity": random.randint(1, 500),
                "itemList_qtyUnit": "KGS",
                "itemList_taxableAmount": round(taxable_amount, 2),
                "itemList_sgstRate": 9.0 if intra_state else 0.0,
                "itemList_cgstRate": 9.0 if intra_state else 0.0,
                "itemList_igstRate": 0.0 if intra_state else 18.0,
                "itemList_cessRate": 0.0,
                "itemList_cessNonAdvol": 0.0,
                "totalValue": round(taxable_amount, 2),
                "cgstValue": cgst_value,
                "sgstValue": sgst_value,
                "igstValue": igst_value,
                "cessValue": cess_value,
                "TotNonAdvolVal": 0.0,
                "OthValue": oth_value,
                "totInvValue": tot_inv_value,
                "synthetic_batch_id": "batch_001",
            })

    return pl.DataFrame(records)



def _hash_user_id(raw_id: str) -> str:
    return "u_" + hashlib.sha256(raw_id.encode()).hexdigest()[:8]


def _gen_upi_id(name: str) -> str:
    slug = name.lower().replace(" ", "")[:10]
    return f"{slug}@{random.choice(BANK_HANDLES)}"


class UserProfile:
    def __init__(self, user_index: int, persona: str = "genuine_healthy", seed: int = 42):
        rng = random.Random(seed + user_index)
        self.user_id = f"u_{user_index:04d}"
        self.persona = persona
        self.profile_type = persona.upper()
        # MSME fields
        self.state_code = rng.choice(STATE_CODES)
        # Use simple business name
        self.business_name = f"Business {user_index}"
        # Since fake is not available here, generate gstin manually or use fake logic later. 
        pan_letters = "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
        pan_digits = "".join(rng.choices("0123456789", k=4))
        pan_letter_b = rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        self.gstin = f"{self.state_code:02d}{pan_letters}{pan_digits}{pan_letter_b}{rng.randint(1,9)}Z{rng.randint(0,9)}"
        self.vpa = f"biz{user_index}@oksbi"
        self.hsn_sector = rng.choice(list(HSN_SECTORS.keys()))

        # persona-aware defaults so shell_circular has higher upi_daily_rate
        _rates = {
            "genuine_healthy":   (2.0, 1.0, 0.05, 2),
            "genuine_struggling":(1.5, 0.8, 0.20, 3),
            "shell_circular":    (8.0, 4.0, 0.01, 1),
            "paper_trader":      (10.0, 1.0, 0.05, 1),
            "new_to_credit":     (1.5, 0.8, 0.08, 1),
        }
        upi_r, bank_r, emi_p, n_e = _rates.get(persona, (2.0, 1.0, 0.05, 2))
        self.monthly_income = rng.randint(30000, 150000)
        self.upi_id = f"u_{user_index:04d}@oksbi"
        self.name = f"User {user_index}"
        self.age_months = 12
        self.upi_daily_rate = upi_r
        self.bank_txn_per_day = bank_r
        self.emi_overdue_prob = emi_p
        self.n_emis = n_e
        self.city_tier = 1
        self.circular_ring_id = None
        self.age_group = "26-35"
        self.income_band = "mid"
        self.created_at = REFERENCE_DATE.isoformat()


def build_profile(user_index: int, seed: int = 42) -> UserProfile:
    random.seed(seed)
    persona = random.choice(PERSONA_TYPES)
    return UserProfile(user_index, persona, seed)


def generate_all_events(profile: UserProfile, history_months: int = 12, reference_date: datetime = None):
    """Compatibility wrapper for tests."""
    from src.ingestion.schemas import CanonicalEvent
    from datetime import timedelta
    
    ref = reference_date or REFERENCE_DATE
    
    # Simple mapping to dict profile
    p_dict = {
        "user_id": profile.user_id,
        "upi_id": profile.upi_id,
        "name": profile.name,
        "profile_type": profile.profile_type,
        "age_months": profile.age_months,
        "monthly_income": profile.monthly_income,
        "upi_daily_rate": profile.upi_daily_rate,
        "bank_txn_per_day": profile.bank_txn_per_day,
        "emi_overdue_prob": profile.emi_overdue_prob,
        "n_emis": profile.n_emis,
        "city_tier": profile.city_tier,
        "age_group": "26-35",
        "income_band": "mid",
        "circular_ring_id": None,
        "created_at": (ref - timedelta(days=history_months*30)).isoformat(),
    }
    
    # We call these but we don't need sorting across all sources for small test volumes
    bank_df = generate_bank_transactions([p_dict])
    upi_df = generate_upi_transactions([p_dict])
    emi_df = generate_emi_schedules([p_dict])
    
    # Fields present in some source DFs but absent from CanonicalEvent
    _EXTRA_COLS = {
        "direction", "counterparty_upi", "txn_type", "next_due_date",
        "schedule_type", "recurrence_pattern", "remaining_tenure",
        "balance", "account_type", "extracted_amount", "extracted_merchant",
        "extracted_type", "confidence_score", "alert_type", "raw_text",
        "upi_id", "name",
    }
    # Normalise status values from generator (lowercase / UPI-specific) → CanonicalEvent enum
    _STATUS_MAP = {
        "success": "SUCCESS",
        "pending": "PENDING",
        "failed": "FAILED",
        "failed_technical": "FAILED",
        "failed_funds": "FAILED",
        "active": "SUCCESS",
        "paid": "SUCCESS",
        "overdue": "FAILED",
        "cancelled": "FAILED",
    }

    def _row_to_event(row: dict, provenance: str, channel: str | None = None) -> CanonicalEvent:
        """Build CanonicalEvent from a raw row dict, overriding provenance/channel."""
        row = dict(row)
        # drop source-specific fields CanonicalEvent doesn't have
        for col in _EXTRA_COLS:
            row.pop(col, None)
        row.pop("source_provenance", None)
        row.pop("channel", None)
        # normalise status
        raw_status = str(row.get("status", "SUCCESS")).lower()
        row["status"] = _STATUS_MAP.get(raw_status, "SUCCESS")
        kwargs: dict = {"source_provenance": provenance}
        if channel:
            kwargs["channel"] = channel
        return CanonicalEvent(**row, **kwargs)

    events = []
    for row in bank_df.to_dicts():
        events.append(_row_to_event(row, "bank_api"))
    for row in upi_df.to_dicts():
        events.append(_row_to_event(row, "upi_api", "UPI"))
    for row in emi_df.to_dicts():
        events.append(_row_to_event(row, "emi_statement", "EMI"))

    # SMS alerts from bank/upi
    for row in bank_df.limit(10).to_dicts():
        if row["amount"] < 0:
            events.append(_row_to_event(row, "sms_parser", "OTHER"))
    
    events.sort(key=lambda x: x.timestamp)
    return events


def _lognormal(mu: float, sigma: float, lo: float = 10.0, hi: float = 5_000_000.0) -> float:
    return float(np.clip(np.random.lognormal(mu, sigma), lo, hi))


def _sample_timestamps(start: datetime, end: datetime, n: int, burst: bool = False) -> list[datetime]:
    """
    Exponential inter-arrivals (genuine) or Gaussian burst clusters (fraud).
    Mirrors CreditIQ sample_timestamps exactly.
    """
    if n <= 0:
        return []
    total_seconds = (end - start).total_seconds()

    if burst:
        n_bursts = random.randint(2, 3)
        centers = sorted(random.uniform(0.15, 0.85) * total_seconds for _ in range(n_bursts))
        burst_width = total_seconds * 0.04
        ts_list: list[datetime] = []
        for k in range(n):
            center = centers[k % n_bursts]
            offset = center + random.gauss(0, burst_width)
            offset = max(0.0, min(total_seconds - 1.0, offset))
            ts_list.append(start + timedelta(seconds=offset))
        return sorted(ts_list)

    intervals = np.random.exponential(scale=total_seconds / max(n, 1), size=n)
    cumulative = np.cumsum(intervals)
    if cumulative[-1] > 0:
        cumulative = cumulative * (total_seconds / cumulative[-1])
    return sorted(start + timedelta(seconds=float(s)) for s in cumulative)


def _get_active_period(age_months: int) -> tuple[datetime, datetime]:
    end_dt = REFERENCE_DATE
    start_dt = end_dt - timedelta(days=age_months * 30)
    return start_dt, end_dt


def _pick(category: str) -> str:
    return random.choice(MERCHANT_TEMPLATES.get(category, ["Unknown"]))


# ── SDV profile synthesis (mirrors CreditIQ build_profiles_sdv) ───────────────

def build_profiles(fake: Faker, n_profiles: int = N_PROFILES) -> list[dict]:
    """
    SDV GaussianCopulaSynthesizer → n_profiles rows with correlated parameters.
    Falls back to manual sampling if SDV unavailable.
    """
    try:
        import pandas as pd
        from sdv.single_table import GaussianCopulaSynthesizer
        from sdv.metadata import Metadata
        return _build_profiles_sdv(fake, n_profiles, pd, GaussianCopulaSynthesizer, Metadata)
    except ImportError:
        logger.warning("[generator] sdv not available — falling back to manual profiles")
        return _build_profiles_manual(fake, n_profiles)


def _build_profiles_sdv(fake, n_profiles, pd, GaussianCopulaSynthesizer, Metadata) -> list[dict]:
    logger.info("[generator] building profiles with SDV Gaussian copula synthesis")

    # Archetype parameters: (lo, hi, std) per field per persona
    archetype_params: dict[str, dict] = {
        "GENUINE_HEALTHY": {
            "age_months": (18, 36, 6),
            "monthly_income": (40_000, 300_000, 60_000),
            "upi_daily_rate": (2.0, 6.0, 1.0),
            "bank_txn_per_day": (1.0, 3.0, 0.5),
            "emi_overdue_prob": (0.01, 0.05, 0.01),
            "n_emis": (1, 3, 0.5),
        },
        "GENUINE_STRUGGLING": {
            "age_months": (8, 30, 8),
            "monthly_income": (10_000, 80_000, 20_000),
            "upi_daily_rate": (0.5, 2.0, 0.5),
            "bank_txn_per_day": (0.5, 1.5, 0.3),
            "emi_overdue_prob": (0.15, 0.35, 0.07),
            "n_emis": (2, 5, 1.0),
        },
        "SHELL_CIRCULAR": {
            "age_months": (14, 28, 5),
            "monthly_income": (80_000, 1_000_000, 200_000),
            "upi_daily_rate": (5.0, 15.0, 3.0),
            "bank_txn_per_day": (3.0, 8.0, 1.5),
            "emi_overdue_prob": (0.00, 0.02, 0.005),
            "n_emis": (0, 1, 0.3),
        },
        "PAPER_TRADER": {
            "age_months": (8, 22, 5),
            "monthly_income": (15_000, 200_000, 50_000),
            "upi_daily_rate": (8.0, 25.0, 5.0),
            "bank_txn_per_day": (0.5, 2.0, 0.4),
            "emi_overdue_prob": (0.03, 0.10, 0.02),
            "n_emis": (1, 2, 0.5),
        },
        "NEW_TO_CREDIT": {
            "age_months": (1, 6, 1.5),
            "monthly_income": (15_000, 100_000, 25_000),
            "upi_daily_rate": (1.0, 4.0, 1.0),
            "bank_txn_per_day": (0.5, 1.5, 0.3),
            "emi_overdue_prob": (0.05, 0.12, 0.03),
            "n_emis": (0, 2, 0.5),
        },
    }

    seed_rows: list[dict] = []
    for ptype, params in archetype_params.items():
        for _ in range(10):
            row: dict = {"profile_type": ptype}
            for field, (lo, hi, std) in params.items():
                val = np.clip(np.random.normal((lo + hi) / 2.0, std), lo, hi)
                row[field] = round(float(val), 4)
            seed_rows.append(row)

    seed_df = pd.DataFrame(seed_rows)
    metadata = Metadata()
    metadata.detect_table_from_dataframe(table_name="profiles", data=seed_df)
    metadata.update_column(column_name="profile_type", table_name="profiles", sdtype="categorical")

    synth = GaussianCopulaSynthesizer(metadata)
    synth.fit(seed_df)
    sampled = synth.sample(num_rows=n_profiles)
    logger.info(f"[generator] SDV sampled {len(sampled)} profiles")

    profiles: list[dict] = []
    ring_vpas: dict[str, list[str]] = {}
    ring_counter = [1]  # mutable ref

    for _, row in sampled.iterrows():
        ptype = str(row["profile_type"])
        raw_id = f"user_{len(profiles):04d}"
        user_id = _hash_user_id(raw_id)
        name = fake.name()
        upi_id = _gen_upi_id(name)
        age = max(1, int(round(float(row["age_months"]))))
        income = max(5000.0, float(row["monthly_income"]))
        city_tier = int(random.choices([1, 2, 3, 4], weights=[0.3, 0.3, 0.25, 0.15])[0])
        age_group = random.choice(["18-25", "26-35", "36-45", "46-55", "55+"])
        income_band = "low" if income < 50_000 else ("mid" if income < 100_000 else "high")

        profiles.append({
            "user_id": user_id,
            "upi_id": upi_id,
            "name": name,
            "profile_type": ptype,
            "age_months": age,
            "monthly_income": round(income, 2),
            "upi_daily_rate": float(np.clip(row["upi_daily_rate"], 0.1, 30.0)),
            "bank_txn_per_day": float(np.clip(row["bank_txn_per_day"], 0.1, 10.0)),
            "emi_overdue_prob": float(np.clip(row["emi_overdue_prob"], 0.0, 1.0)),
            "n_emis": max(0, int(round(float(row["n_emis"])))),
            "city_tier": city_tier,
            "age_group": age_group,
            "income_band": income_band,
            "circular_ring_id": None,
            "created_at": REFERENCE_DATE.isoformat(),
            "state_code": random.choice(STATE_CODES),
            "business_name": fake.company(),
            "gstin": generate_gstin(random.choice(STATE_CODES), fake),
            "vpa": _gen_upi_id(fake.company()),
            "hsn_sector": random.choice(list(HSN_SECTORS.keys())),

        })

    # assign ring IDs to SHELL_CIRCULAR profiles
    shell_idx = [i for i, p in enumerate(profiles) if p["profile_type"] == "SHELL_CIRCULAR"]
    random.shuffle(shell_idx)
    i = 0
    while i < len(shell_idx):
        chunk_size = 4 if (len(shell_idx) - i) >= 4 else 3
        chunk = shell_idx[i : i + chunk_size]
        if len(chunk) < 3:
            break
        ring_id = f"ring_{ring_counter[0]:03d}"
        ring_counter[0] += 1
        ring_upi = [profiles[idx]["upi_id"] for idx in chunk]
        ring_vpas[ring_id] = ring_upi
        for idx in chunk:
            profiles[idx]["circular_ring_id"] = ring_id
        i += chunk_size

    return profiles


def _build_profiles_manual(fake: Faker, n_profiles: int = N_PROFILES) -> list[dict]:
    """Fallback: plain random sampling without SDV."""
    params_map: dict[str, dict] = {
        "GENUINE_HEALTHY":   dict(income_mu=10.8, income_sigma=0.8, age=(18,36), upi=(2,6), bank=(1,3), emi_prob=0.03, n_emis=(1,3)),
        "GENUINE_STRUGGLING":dict(income_mu=9.8,  income_sigma=0.9, age=(8,30),  upi=(0.5,2), bank=(0.5,1.5), emi_prob=0.20, n_emis=(2,5)),
        "SHELL_CIRCULAR":    dict(income_mu=11.5, income_sigma=0.5, age=(14,28), upi=(5,15), bank=(3,8), emi_prob=0.01, n_emis=(0,1)),
        "PAPER_TRADER":      dict(income_mu=10.5, income_sigma=1.0, age=(8,22),  upi=(8,25), bank=(0.5,2), emi_prob=0.05, n_emis=(1,2)),
        "NEW_TO_CREDIT":     dict(income_mu=10.0, income_sigma=0.7, age=(1,6),   upi=(1,4), bank=(0.5,1.5), emi_prob=0.08, n_emis=(0,2)),
    }
    assignments = random.choices(PROFILE_TYPES, weights=PROFILE_WEIGHTS, k=n_profiles)
    profiles: list[dict] = []
    for idx, ptype in enumerate(assignments):
        p = params_map[ptype]
        raw_id = f"user_{idx:04d}"
        user_id = _hash_user_id(raw_id)
        name = fake.name()
        upi_id = _gen_upi_id(name)
        income = _lognormal(p["income_mu"], p["income_sigma"], 5000, 5_000_000)
        age = random.randint(*p["age"])
        city_tier = int(random.choices([1, 2, 3, 4], weights=[0.3, 0.3, 0.25, 0.15])[0])
        age_group = random.choice(["18-25", "26-35", "36-45", "46-55", "55+"])
        income_band = "low" if income < 50_000 else ("mid" if income < 100_000 else "high")
        profiles.append({
            "user_id": user_id,
            "upi_id": upi_id,
            "name": name,
            "profile_type": ptype,
            "age_months": age,
            "monthly_income": round(income, 2),
            "upi_daily_rate": random.uniform(*p["upi"]),
            "bank_txn_per_day": random.uniform(*p["bank"]),
            "emi_overdue_prob": p["emi_prob"],
            "n_emis": random.randint(*p["n_emis"]),
            "city_tier": city_tier,
            "age_group": age_group,
            "income_band": income_band,
            "circular_ring_id": None,
            "created_at": REFERENCE_DATE.isoformat(),
            "state_code": random.choice(STATE_CODES),
            "business_name": fake.company(),
            "gstin": generate_gstin(random.choice(STATE_CODES), fake),
            "vpa": _gen_upi_id(fake.company()),
            "hsn_sector": random.choice(list(HSN_SECTORS.keys())),

        })

    # ring IDs
    shell_idx = [i for i, p in enumerate(profiles) if p["profile_type"] == "SHELL_CIRCULAR"]
    random.shuffle(shell_idx)
    i = 0
    ring_c = 1
    while i < len(shell_idx):
        cs = 4 if (len(shell_idx) - i) >= 4 else 3
        chunk = shell_idx[i : i + cs]
        if len(chunk) < 3:
            break
        for idx in chunk:
            profiles[idx]["circular_ring_id"] = f"ring_{ring_c:03d}"
        ring_c += 1
        i += cs

    return profiles


# ── per-source generators ─────────────────────────────────────────────────────

def generate_bank_transactions(profiles: list[dict] | dict | UserProfile, *args, **kwargs) -> pl.DataFrame:
    records: list[dict] = []
    if isinstance(profiles, UserProfile):
        profiles = [profiles.__dict__]
    if isinstance(profiles, dict):
        profiles = [profiles]
    
    # Handle case where profiles is a list of UserProfile objects
    if profiles and not isinstance(profiles[0], dict):
        profiles = [p.__dict__ if hasattr(p, "__dict__") else p for p in profiles]

    logger.info("[generator] generating bank transactions")
    for p in tqdm(profiles, desc="Bank Simulation", unit="user"):
        ptype = p["profile_type"]
        age = p["age_months"]
        income = p["monthly_income"]
        start_dt, end_dt = _get_active_period(age)

        # lognormal params per persona (matches CreditIQ)
        lmu_map = {"GENUINE_HEALTHY": (10.8, 0.8), "GENUINE_STRUGGLING": (9.9, 1.2),
                   "SHELL_CIRCULAR": (12.2, 0.4), "PAPER_TRADER": (12.6, 0.3), "NEW_TO_CREDIT": (9.6, 1.5)}
        exp_mu, exp_sigma = lmu_map.get(ptype, (10.5, 1.0))

        # salary credits on ~1st of each month
        cur = start_dt.replace(day=1)
        balance = income * 2.0
        while cur < end_dt:
            salary = income * random.uniform(0.92, 1.05)
            balance += salary
            records.append({
                "user_id": p["user_id"],
                "event_id": str(uuid.uuid4()),
                "timestamp": (cur + timedelta(hours=random.uniform(9, 12))).isoformat(),
                "amount": round(salary, 2),
                "merchant_name": _pick("SALARY"),
                "channel": "BANK_TRANSFER",
                "balance_after": round(balance, 2),
                "reference_id": f"SAL{cur.strftime('%Y%m')}",
                "source_provenance": "bank_api",
                "status": "SUCCESS",
                "recurrence_flag": False,
            })
            if random.random() < 0.01: # Sample 1% for live stream
                logger.info(f"[simulation] [BANK] User {p['user_id'][:8]} received salary: ₹{salary:,.2f}", extra={"markup": True, "style": "simulation"})
            if cur.month == 12:
                cur = cur.replace(year=cur.year + 1, month=1)
            else:
                cur = cur.replace(month=cur.month + 1)

        # expense transactions
        n_exp = int(age * p["bank_txn_per_day"] * 30)
        is_burst = ptype == "SHELL_CIRCULAR"
        timestamps = _sample_timestamps(start_dt, end_dt, n_exp, burst=is_burst)

        exp_cats = ["GROCERY", "BILLS_UTILITIES", "TRANSPORT", "HEALTHCARE", "DINING", "ENTERTAINMENT"]
        for ts in timestamps:
            cat = random.choice(exp_cats)
            amt = _lognormal(exp_mu - 3, exp_sigma, 50, 50_000)
            balance -= amt
            status = random.choices(
                ["SUCCESS", "FAILED"],
                weights=[0.97 if ptype == "GENUINE_HEALTHY" else 0.88, 0.03 if ptype == "GENUINE_HEALTHY" else 0.12]
            )[0]
            records.append({
                "user_id": p["user_id"],
                "event_id": str(uuid.uuid4()),
                "timestamp": ts.isoformat(),
                "amount": -round(amt, 2),
                "merchant_name": _pick(cat),
                "channel": random.choices(["CARD", "BANK_TRANSFER"], weights=[0.6, 0.4])[0],
                "balance_after": round(max(balance, 0), 2),
                "reference_id": f"TXN{uuid.uuid4().hex[:8].upper()}",
                "source_provenance": "bank_api",
                "status": status,
                "recurrence_flag": False,
            })

    df = pl.DataFrame(records)
    logger.info(f"[generator] bank transactions: {len(df):,} rows")
    return df


def generate_upi_transactions(profiles: list[dict] | dict | UserProfile, *args, **kwargs) -> pl.DataFrame:
    records: list[dict] = []
    if isinstance(profiles, UserProfile):
        profiles = [profiles.__dict__]
    if isinstance(profiles, dict):
        profiles = [profiles]
    
    if profiles and not isinstance(profiles[0], dict):
        profiles = [p.__dict__ if hasattr(p, "__dict__") else p for p in profiles]
    all_upi_ids = [p["upi_id"] for p in profiles]

    # build ring vpa maps
    ring_vpas: dict[str, list[str]] = {}
    ring_pos: dict[str, int] = {}
    for p in profiles:
        rid = p.get("circular_ring_id")
        if rid:
            if rid not in ring_vpas:
                ring_vpas[rid] = []
            ring_pos[p["user_id"]] = len(ring_vpas[rid])
            ring_vpas[rid].append(p["upi_id"])

    lmu_map = {"GENUINE_HEALTHY": (9.5, 0.9), "GENUINE_STRUGGLING": (8.8, 1.1),
               "SHELL_CIRCULAR": (11.5, 0.5), "PAPER_TRADER": (10.0, 0.7), "NEW_TO_CREDIT": (8.2, 1.3)}
    p2m_map = {"GENUINE_HEALTHY": 0.70, "GENUINE_STRUGGLING": 0.45,
               "SHELL_CIRCULAR": 0.0, "PAPER_TRADER": 0.30, "NEW_TO_CREDIT": 0.55}
    inbound_map = {"GENUINE_HEALTHY": 0.57, "GENUINE_STRUGGLING": 0.50,
                   "SHELL_CIRCULAR": 0.50, "PAPER_TRADER": 0.50, "NEW_TO_CREDIT": 0.50}
    status_weights_map = {
        "GENUINE_HEALTHY": [0.97, 0.02, 0.01],
        "GENUINE_STRUGGLING": [0.89, 0.03, 0.08],
        "SHELL_CIRCULAR": [0.98, 0.01, 0.01],
        "PAPER_TRADER": [0.93, 0.03, 0.04],
        "NEW_TO_CREDIT": [0.92, 0.04, 0.04],
    }

    logger.info("[generator] generating UPI transactions")
    for p in tqdm(profiles, desc="UPI Simulation", unit="user"):
        ptype = p["profile_type"]
        age = p["age_months"]
        start_dt, end_dt = _get_active_period(age)

        n_txns = int(age * p["upi_daily_rate"] * 30)
        is_burst = ptype == "SHELL_CIRCULAR"
        timestamps = _sample_timestamps(start_dt, end_dt, n_txns, burst=is_burst)

        mu, sigma = lmu_map.get(ptype, (9.5, 1.0))
        p2m = p2m_map.get(ptype, 0.5)
        p_inbound = inbound_map.get(ptype, 0.5)
        sw = status_weights_map.get(ptype, [0.93, 0.03, 0.04])

        rid = p.get("circular_ring_id")
        ring_members = ring_vpas.get(rid, []) if rid else []
        pos = ring_pos.get(p["user_id"], 0)

        for ts in timestamps:
            amt = _lognormal(mu, sigma, 10, 500_000)
            if ptype == "PAPER_TRADER":
                amt = min(amt, 999.0)

            direction = random.choices(["inbound", "outbound"], weights=[p_inbound, 1.0 - p_inbound])[0]

            if ptype == "SHELL_CIRCULAR" and ring_members:
                counterparty = ring_members[(pos + 1) % len(ring_members)] if random.random() < 0.70 else random.choice(all_upi_ids)
                txn_type = "p2p"
                cat = "TRANSFER"
            else:
                txn_type = random.choices(["p2m", "p2p"], weights=[p2m, 1.0 - p2m])[0]
                if txn_type == "p2m":
                    cat = random.choices(
                        ["GROCERY", "DINING", "TRANSPORT", "ENTERTAINMENT", "BILLS_UTILITIES", "HEALTHCARE"],
                        weights=[0.25, 0.20, 0.15, 0.10, 0.20, 0.10]
                    )[0]
                    counterparty = f"{cat.lower()}@{random.choice(BANK_HANDLES)}"
                else:
                    cat = "TRANSFER"
                    counterparty = random.choice(all_upi_ids)

            status = random.choices(["success", "failed_technical", "failed_funds"], weights=sw)[0]
            signed_amt = round(amt if direction == "inbound" else -amt, 2)

            records.append({
                "user_id": p["user_id"],
                "event_id": str(uuid.uuid4()),
                "timestamp": ts.isoformat(),
                "amount": signed_amt,
                "direction": direction,
                "merchant_name": _pick(cat),
                "txn_type": txn_type,
                "counterparty_upi": counterparty,
                "status": status,
                "source_provenance": "upi_api",
                "recurrence_flag": False,
            })
            if random.random() < 0.005:  # Sample for live stream
                icon = "↗" if direction == "outbound" else "↙"
                color = "red" if direction == "outbound" else "green"
                logger.info(f"[simulation] [UPI] {icon} {p['user_id'][:8]} {direction}: [{color}]₹{abs(signed_amt):,.2f}[/{color}] to {counterparty} ({cat})", extra={"markup": True, "style": "simulation"})

    df = pl.DataFrame(records)
    logger.info(f"[generator] UPI transactions: {len(df):,} rows")
    return df


def generate_sms_alerts(bank_df: pl.DataFrame, upi_df: pl.DataFrame) -> pl.DataFrame:
    """
    Derive SMS alerts from bank + UPI events with exponential delay (median 30s).
    ~75% coverage rate per CreditIQ approach.
    """
    logger.info("[generator] generating SMS alerts")
    records: list[dict] = []

    for src_df in [bank_df, upi_df]:
        for row in src_df.to_dicts():
            if random.random() > 0.75:
                continue
            delay_s = float(np.random.exponential(30.0))
            ts_base = datetime.fromisoformat(row["timestamp"])
            ts = ts_base + timedelta(seconds=min(delay_s, 120.0))
            amt = row["amount"]
            merchant = row["merchant_name"]
            user_id = row["user_id"]

            if amt > 0:
                alert_type = "CREDIT_ALERT"
                text = f"INR {abs(amt):,.0f} credited to your account on {ts.strftime('%d-%b-%Y')} from {merchant}."
            else:
                alert_type = "DEBIT_ALERT"
                text = f"INR {abs(amt):,.0f} debited on {ts.strftime('%d-%b-%Y')} for {merchant}."

            records.append({
                "user_id": user_id,
                "event_id": str(uuid.uuid4()),
                "timestamp": ts.isoformat(),
                "amount": amt,
                "merchant_name": merchant,
                "alert_type": alert_type,
                "raw_text": text,
                "source_provenance": "sms_parser",
                "status": "SUCCESS",
                "recurrence_flag": False,
            })

    df = pl.DataFrame(records)
    logger.info(f"[generator] SMS alerts: {len(df):,} rows")
    return df


def generate_emi_schedules(profiles: list[dict] | dict | UserProfile, *args, **kwargs) -> pl.DataFrame:
    """EMI + subscription monthly events with overdue logic."""
    if isinstance(profiles, UserProfile):
        profiles = [profiles.__dict__]
    if isinstance(profiles, dict):
        profiles = [profiles]
    
    if profiles and not isinstance(profiles[0], dict):
        profiles = [p.__dict__ if hasattr(p, "__dict__") else p for p in profiles]
    logger.info("[generator] generating EMI schedules")
    records: list[dict] = []

    for p in profiles:
        age = p["age_months"]
        income = p["monthly_income"]
        emi_prob = p["emi_overdue_prob"]
        start_dt, end_dt = _get_active_period(age)
        n_emis = p["n_emis"]

        # EMI loans
        for _ in range(n_emis):
            emi_day = random.randint(1, 28)
            emi_amt = min(_lognormal(9.0, 0.8, 1_000, 200_000), income * 0.50)
            lender = _pick("EMI")
            tenure = random.randint(3, 36)
            overdue = random.random() < emi_prob

            cur = start_dt.replace(day=min(emi_day, 28))
            paid = 0
            while cur < end_dt and paid < tenure:
                delay = int(np.random.negative_binomial(2, 0.15)) if overdue else 0
                fail = overdue and random.random() < 0.3
                records.append({
                    "user_id": p["user_id"],
                    "event_id": str(uuid.uuid4()),
                    "timestamp": (cur + timedelta(days=delay, hours=random.uniform(9, 14))).isoformat(),
                    "amount": -round(emi_amt, 2),
                    "merchant_name": lender,
                    "schedule_type": "EMI_LOAN",
                    "recurrence_pattern": f"MONTHLY_{emi_day}TH",
                    "remaining_tenure": tenure - paid,
                    "emi_status": "OVERDUE" if fail else "PAID",
                    "source_provenance": "emi_statement",
                    "status": "FAILED" if fail else "SUCCESS",
                    "recurrence_flag": True,
                })
                if random.random() < 0.05:
                    status_str = "[bold red]FAILED[/bold red]" if fail else "[bold green]PAID[/bold green]"
                    logger.info(f"[simulation] [EMI] {p['user_id'][:8]} {lender}: ₹{emi_amt:,.2f} -> {status_str}", extra={"markup": True, "style": "simulation"})
                paid += 1
                if cur.month == 12:
                    cur = cur.replace(year=cur.year + 1, month=1)
                else:
                    cur = cur.replace(month=cur.month + 1)

        # subscriptions (1–4 per user)
        n_subs = random.randint(1, 4)
        for _ in range(n_subs):
            sub_day = random.randint(1, 28)
            sub_amt = _lognormal(6.5, 0.8, 99, 5_000)
            provider = _pick("SUBSCRIPTION")
            cur = start_dt.replace(day=min(sub_day, 28))
            while cur < end_dt:
                records.append({
                    "user_id": p["user_id"],
                    "event_id": str(uuid.uuid4()),
                    "timestamp": (cur + timedelta(hours=random.uniform(0, 6))).isoformat(),
                    "amount": -round(sub_amt, 2),
                    "merchant_name": provider,
                    "schedule_type": "SUBSCRIPTION",
                    "recurrence_pattern": f"MONTHLY_{sub_day}TH",
                    "remaining_tenure": 0,
                    "emi_status": "PAID",
                    "source_provenance": "emi_statement",
                    "status": "SUCCESS" if random.random() > 0.05 else "FAILED",
                    "recurrence_flag": True,
                })
                if cur.month == 12:
                    cur = cur.replace(year=cur.year + 1, month=1)
                else:
                    cur = cur.replace(month=cur.month + 1)

    df = pl.DataFrame(records)
    logger.info(f"[generator] EMI schedules: {len(df):,} rows")
    return df


def generate_open_banking(profiles: list[dict]) -> pl.DataFrame:
    """Daily AA-style balance snapshots per user."""
    logger.info("[generator] generating open-banking feeds")
    records: list[dict] = []

    for p in profiles:
        age = p["age_months"]
        income = p["monthly_income"]
        start_dt, end_dt = _get_active_period(age)

        balance = income * random.uniform(1.0, 3.0)
        cur = start_dt
        while cur < end_dt:
            daily_net = random.gauss(0, income * 0.05)
            balance = max(0.0, balance + daily_net)
            records.append({
                "user_id": p["user_id"],
                "event_id": str(uuid.uuid4()),
                "timestamp": (cur + timedelta(hours=23, minutes=59)).isoformat(),
                "amount": round(daily_net, 2),
                "merchant_name": "AA_BALANCE_SNAPSHOT",
                "balance_after": round(balance, 2),
                "account_type": "SAVINGS",
                "source_provenance": "open_banking_aa",
                "status": "SUCCESS",
                "recurrence_flag": False,
            })
            cur += timedelta(days=1)

    df = pl.DataFrame(records)
    logger.info(f"[generator] open-banking: {len(df):,} rows")
    return df


def generate_voice_transcripts(profiles: list[dict]) -> pl.DataFrame:
    """Sparse voice call transcript events."""
    logger.info("[generator] generating voice transcripts")
    records: list[dict] = []

    for p in profiles:
        age = p["age_months"]
        start_dt, end_dt = _get_active_period(age)
        n = random.randint(0, 5)
        for _ in range(n):
            ts = start_dt + timedelta(days=random.uniform(0, age * 30))
            if ts >= end_dt:
                ts = end_dt - timedelta(hours=1)
            amt = _lognormal(8.5, 1.0, 500, 50_000)
            cat = random.choice(["EMI", "BILLS_UTILITIES"])
            records.append({
                "user_id": p["user_id"],
                "event_id": str(uuid.uuid4()),
                "timestamp": ts.isoformat(),
                "extracted_amount": round(amt, 2),
                "extracted_merchant": _pick(cat),
                "extracted_type": "EMI_PAYMENT" if cat == "EMI" else "BILL_PAYMENT",
                "confidence_score": round(random.uniform(0.45, 0.92), 3),
                "source_provenance": "voice_stt_parser",
                "status": "SUCCESS",
                "recurrence_flag": False,
            })

    df = pl.DataFrame(records)
    logger.info(f"[generator] voice transcripts: {len(df):,} rows")
    return df


# ── Parquet chunk writer (mirrors CreditIQ write_chunks) ──────────────────────

def write_chunks(df: pl.DataFrame, prefix: str, chunk_size: int = CHUNK_SIZE) -> int:
    """Write DataFrame as chunked Parquet files to data/raw/."""
    RAW_DATA_PATH.mkdir(parents=True, exist_ok=True)
    n_rows = len(df)
    if n_rows == 0:
        logger.warning(f"[generator] {prefix}: 0 rows — skipping")
        return 0
    n_chunks = math.ceil(n_rows / chunk_size)
    for i in range(n_chunks):
        chunk = df.slice(i * chunk_size, chunk_size)
        out_path = RAW_DATA_PATH / f"{prefix}_chunk_{i:04d}.parquet"
        chunk.write_parquet(out_path)
    logger.info(f"[generator] {prefix}: {n_rows:,} rows → {n_chunks} chunks")
    return n_chunks


def write_profiles(profiles: list[dict]) -> None:
    RAW_DATA_PATH.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(profiles)
    df.write_parquet(RAW_DATA_PATH / "user_profiles.parquet")
    logger.info(f"[generator] user_profiles.parquet written ({len(profiles)} profiles)")


def event_stream(n_profiles: int = N_PROFILES, history_months: int = 12):
    """
    Generator that creates synthetic financial activity and yields CanonicalEvent objects.
    This is used by the Redis producer to simulate live ingestion.
    """
    from src.ingestion.schemas import CanonicalEvent
    
    sentinel = RAW_DATA_PATH / "user_profiles.parquet"
    if sentinel.exists():
        logger.info("[generator] Loading pre-generated events from data/raw...")
        profiles_df = pl.read_parquet(sentinel)
        profiles = profiles_df.to_dicts()
        
        # Load all chunks and combine
        sources = [
            "bank_transactions", "upi_transactions", "sms_alerts", 
            "emi_schedules", "open_banking", "voice_transcripts"
        ]
        
        dfs = {}
        for s in sources:
            files = list(RAW_DATA_PATH.glob(f"{s}_chunk_*.parquet"))
            if files:
                dfs[s] = pl.concat([pl.read_parquet(f) for f in files])
            else:
                dfs[s] = pl.DataFrame()

        bank_df = dfs.get("bank_transactions", pl.DataFrame())
        upi_df = dfs.get("upi_transactions", pl.DataFrame())
        sms_df = dfs.get("sms_alerts", pl.DataFrame())
        emi_df = dfs.get("emi_schedules", pl.DataFrame())
        ob_df = dfs.get("open_banking", pl.DataFrame())
        voice_df = dfs.get("voice_transcripts", pl.DataFrame())
    else:
        logger.info("[generator] No pre-generated data found. Generating in-memory...")
        # 1. Build profiles
        fake = Faker("en_IN")
        Faker.seed(42)
        np.random.seed(42)
        random.seed(42)
        
        profiles = build_profiles(fake, n_profiles=n_profiles)
        
        # 2. Generate all sources as DataFrames
        bank_df  = generate_bank_transactions(profiles)
        upi_df   = generate_upi_transactions(profiles)
        sms_df   = generate_sms_alerts(bank_df, upi_df)
        emi_df   = generate_emi_schedules(profiles)
        ob_df    = generate_open_banking(profiles)
        voice_df = generate_voice_transcripts(profiles)
    
    # 3. Normalise and yield as events
    all_events: list[dict] = []
    
    # Bank
    if not bank_df.is_empty():
        for row in bank_df.to_dicts():
            all_events.append({
                "event_id": row["event_id"],
                "user_id": row["user_id"],
                "timestamp": row["timestamp"],
                "amount": row["amount"],
                "merchant_name": row["merchant_name"],
                "channel": row["channel"],
                "balance_after": row["balance_after"],
                "reference_id": row["reference_id"],
                "source_provenance": "bank_api",
                "status": row["status"],
                "recurrence_flag": row["recurrence_flag"],
            })
        
    # UPI
    if not upi_df.is_empty():
        for row in upi_df.to_dicts():
            all_events.append({
                "event_id": row["event_id"],
                "user_id": row["user_id"],
                "timestamp": row["timestamp"],
                "amount": row["amount"],
            "merchant_name": row["merchant_name"],
            "channel": "UPI",
            "reference_id": row["event_id"][:8],
            "source_provenance": "upi_api",
            "status": "SUCCESS" if row["status"] == "success" else "FAILED",
            "recurrence_flag": row["recurrence_flag"],
        })
        
    # SMS
    for row in sms_df.to_dicts():
        all_events.append({
            "event_id": row["event_id"],
            "user_id": row["user_id"],
            "timestamp": row["timestamp"],
            "amount": row["amount"],
            "merchant_name": row["merchant_name"],
            "source_provenance": "sms_parser",
            "status": row["status"],
            "recurrence_flag": row["recurrence_flag"],
        })
        
    # EMI
    for row in emi_df.to_dicts():
        all_events.append({
            "event_id": row["event_id"],
            "user_id": row["user_id"],
            "timestamp": row["timestamp"],
            "amount": row["amount"],
            "merchant_name": row["merchant_name"],
            "channel": "EMI",
            "source_provenance": "emi_statement",
            "status": row["status"],
            "recurrence_flag": row["recurrence_flag"],
        })
        
    # Open Banking
    for row in ob_df.to_dicts():
        all_events.append({
            "event_id": row["event_id"],
            "user_id": row["user_id"],
            "timestamp": row["timestamp"],
            "amount": row["amount"],
            "merchant_name": row["merchant_name"],
            "balance_after": row["balance_after"],
            "source_provenance": "open_banking_aa",
            "status": row["status"],
            "recurrence_flag": row["recurrence_flag"],
        })
        
    # Voice
    for row in voice_df.to_dicts():
        all_events.append({
            "event_id": row["event_id"],
            "user_id": row["user_id"],
            "timestamp": row["timestamp"],
            "amount": row["extracted_amount"],
            "merchant_name": row["extracted_merchant"],
            "source_provenance": "voice_stt_parser",
            "status": row["status"],
            "recurrence_flag": row["recurrence_flag"],
        })
        
    # Sort and Stream
    all_events.sort(key=lambda x: x["timestamp"])
    
    for ev_dict in all_events:
        yield CanonicalEvent(**ev_dict)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Airavat Phase 1: Synthetic Data Generation")
    parser.add_argument("--force", action="store_true",
                        help="Wipe existing data/raw and regenerate from scratch")
    args = parser.parse_args()

    console.print("=" * 60, style="bold cyan")
    console.print(" Airavat — Phase 1: Synthetic Data Generation", style="bold green")
    console.print("=" * 60, style="bold cyan")

    # ── cache check: skip if data already exists and --force not set ──────────
    sentinel = RAW_DATA_PATH / "user_profiles.parquet"
    if sentinel.exists() and not args.force:
        existing = list(RAW_DATA_PATH.glob("*_chunk_*.parquet"))
        console.print(
            f"[yellow]⚡ data/raw already exists ({len(existing)} chunk files). "
            f"Skipping generation. Pass --force to regenerate.[/yellow]"
        )
        raise SystemExit(0)

    # wipe previous data only when forced or first run
    for d in [RAW_DATA_PATH, Path("data/features"), Path("data/models")]:
        if d.exists():
            shutil.rmtree(d)
            logger.info(f"[generator] wiped {d}")

    # seed for reproducibility
    Faker.seed(42)
    np.random.seed(42)
    random.seed(42)

    fake = Faker("en_IN")

    logger.info(f"\n[generator] building {N_PROFILES} user profiles via SDV copula")
    profiles = build_profiles(fake, n_profiles=N_PROFILES)
    write_profiles(profiles)


    bank_df  = generate_bank_transactions(profiles)
    upi_df   = generate_upi_transactions(profiles)
    sms_df   = generate_sms_alerts(bank_df, upi_df)
    emi_df   = generate_emi_schedules(profiles)
    ob_df    = generate_open_banking(profiles)
    voice_df = generate_voice_transcripts(profiles)
    
    # MSME data
    import faker
    fake = faker.Faker("en_IN")
    faker.Faker.seed(42)
    gst_df = generate_gst_invoices(profiles, fake)
    ewb_df = generate_eway_bills(profiles, fake)

    write_chunks(bank_df,  "bank_transactions")
    write_chunks(upi_df,   "upi_transactions")
    write_chunks(sms_df,   "sms_alerts")
    write_chunks(emi_df,   "emi_schedules")
    write_chunks(ob_df,    "open_banking")
    write_chunks(voice_df, "voice_transcripts")
    write_chunks(gst_df, "gst_invoices")
    write_chunks(ewb_df, "eway_bills")


    total = len(bank_df) + len(upi_df) + len(sms_df) + len(emi_df) + len(ob_df) + len(voice_df)
    logger.info(f"\n[generator] [bold green]✓ generation complete — {total:,} total records across 6 sources[/bold green]", extra={"markup": True})
    logger.info(f"[generator] profiles: {len(profiles)}")
    logger.info(f"[generator] bank: {len(bank_df):,}  upi: {len(upi_df):,}  sms: {len(sms_df):,}")
    logger.info(f"[generator] emi: {len(emi_df):,}  open_banking: {len(ob_df):,}  voice: {len(voice_df):,}")
