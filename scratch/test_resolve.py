import asyncio
import polars as pl
from pathlib import Path

# Mock a Request-like object for app.state.redis
class MockApp:
    def __init__(self):
        self.state = type('State', (), {'redis': None})()

class MockRequest:
    def __init__(self):
        self.app = MockApp()

# Simplified _resolve_entity_ids (since we can't easily import the one with _STORE)
def test_resolve(identifier):
    ids = {identifier}
    p_path = Path("data/raw/user_profiles.parquet")
    if p_path.exists():
        df_u = pl.read_parquet(p_path)
        match = df_u.filter(
            (pl.col("gstin") == identifier) | 
            (pl.col("user_id") == identifier) | 
            (pl.col("vpa") == identifier) | 
            (pl.col("upi_id") == identifier)
        ).to_dicts()
        if match:
            row = match[0]
            ids.add(row["user_id"])
            if row.get("gstin"): ids.add(row["gstin"])
            if row.get("vpa"): ids.add(row["vpa"])
            if row.get("upi_id"): ids.add(row["upi_id"])
    return ids

print(f"Resolving 09DCTOP0026R4Z8: {test_resolve('09DCTOP0026R4Z8')}")
