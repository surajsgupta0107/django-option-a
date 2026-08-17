import io
import re
from typing import List, Dict, Any

import pandas as pd

# Same matching strategy as the frontend prototype's client-side parser (kept in sync
# intentionally): exact-normalized header match first, substring fallback second, so a
# column like "Configured vCPU" never gets mistaken for a CPU-utilization column just
# because "vCPU" contains "cpu".
FIELD_CANDIDATES = {
    "name": ["name", "servername", "hostname", "server", "host"],
    "application": ["system", "application", "app", "appname"],
    "owner": ["owner", "appowner", "ownername", "contact"],
    "owner_email": ["owneremail", "email", "contactemail"],
    "company": ["company", "client", "businessunit"],
    "description": ["serverdescription", "description", "notes"],
    "environment": ["environmentrob", "environment", "env"],
    "cpu_pct": ["cpuusageavg", "cpuutilization", "cpuutil", "cpupercent", "cpu"],
    "memory_pct": ["memoryusageavg", "memoryutilization", "memutil", "memorypercent", "ram", "memory"],
    "storage_pct": ["storageusageavg", "storageutilization", "diskutil", "storagepercent", "disk", "storage"],
    "cpu_allocated": ["configuredvcpu", "allocatedvcpu", "vcpu", "cpucores", "allocatedcpu"],
    "mem_allocated_gb": ["configuredmemory", "allocatedmemorygb", "ramgb", "memorygb", "allocatedmemory"],
    "storage_allocated_gb": ["configuredstoragegb", "allocatedstoragegb", "storagegb", "diskgb", "allocatedstorage"],
    "reclaimable_vcpu": ["reclaimablevcpu", "reclaimablevcpus"],
    "reclaimable_memory_gb": ["reclaimablememory"],
}


def normalize_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(h or "").lower())


def build_header_map(headers: List[str]) -> Dict[str, str]:
    norm = [normalize_header(h) for h in headers]
    mapping: Dict[str, str] = {}
    # pass 1: exact match
    for field, candidates in FIELD_CANDIDATES.items():
        for cand in candidates:
            if cand in norm:
                mapping[field] = headers[norm.index(cand)]
                break
    # pass 2: substring fallback
    for field, candidates in FIELD_CANDIDATES.items():
        if field in mapping:
            continue
        for cand in candidates:
            idx = next((i for i, h in enumerate(norm) if cand in h), None)
            if idx is not None:
                mapping[field] = headers[idx]
                break
    return mapping


def _num(v, default=None):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "-"):
        return default
    try:
        cleaned = re.sub(r"[^0-9.\-]", "", str(v))
        return float(cleaned) if cleaned not in ("", "-", ".") else default
    except (ValueError, TypeError):
        return default


def parse_upload(filename: str, content: bytes) -> List[Dict[str, Any]]:
    """Parses a CSV or Excel upload into a list of dicts matching the Server model fields."""
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content), dtype=str)
    else:
        df = pd.read_csv(io.BytesIO(content), dtype=str)

    df = df.dropna(how="all")
    headers = list(df.columns)
    field_map = build_header_map(headers)

    records = []
    for _, row in df.iterrows():
        def col(field):
            h = field_map.get(field)
            return row[h] if h and h in row else None

        cpu = _num(col("cpu_pct"), 0) or 0
        memory = _num(col("memory_pct"), 0) or 0
        storage = _num(col("storage_pct"), None)

        records.append({
            "name": str(col("name")) if col("name") is not None else None,
            "application": str(col("application")) if col("application") is not None else "Unassigned",
            "owner": str(col("owner")) if col("owner") is not None else "Unassigned",
            # "owner_email": str(col("owner_email")) if col("owner_email") is not None else "unknown@company.com",
            "owner_email": str(col("owner_email")) if col("owner_email") is not None else "surajsgupta0107@gmail.com",
            "company": str(col("company")) if col("company") is not None else None,
            "description": str(col("description")) if col("description") is not None else None,
            "environment": str(col("environment")) if col("environment") is not None else "Production",
            "cpu_pct": max(0, min(100, cpu)),
            "memory_pct": max(0, min(100, memory)),
            "storage_pct": max(0, min(100, storage)) if storage is not None else None,
            "cpu_allocated": _num(col("cpu_allocated"), 4),
            "mem_allocated_gb": _num(col("mem_allocated_gb"), 16),
            "storage_allocated_gb": _num(col("storage_allocated_gb"), None),
            "reclaimable_vcpu": _num(col("reclaimable_vcpu"), None),
            "reclaimable_memory_gb": _num(col("reclaimable_memory_gb"), None),
        })
    return [r for r in records if r["name"]]
