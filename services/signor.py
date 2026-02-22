"""
SIGNOR REST API integration service.

Fetches protein signaling interaction data from the SIGNOR database
(https://signor.uniroma2.it) via their getData.php TSV endpoint.
"""
from __future__ import annotations

from typing import Optional

import requests

from core.config import get_settings
from core.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

SIGNOR_BASE = "https://signor.uniroma2.it/getData.php"

TSV_COLUMNS = [
    "entity_a", "type_a", "id_a", "database_a",
    "entity_b", "type_b", "id_b", "database_b",
    "effect", "mechanism", "residue", "sequence",
    "tax_id", "cell_data", "tissue_data",
    "modulator_complex", "target_complex",
    "modification_a", "modaseq", "modification_b", "modbseq",
    "pmid", "direct", "notes", "annotator", "sentence",
    "signor_id", "score",
]


class SignorServiceError(Exception):
    pass


def fetch_signor_data(uniprot_accession: str) -> Optional[dict]:
    """
    Query SIGNOR for all interactions involving the given UniProt accession.
    Returns a structured dict with interactions, modifications, and metadata,
    or None if no data is found.
    """
    rows = _fetch_tsv(uniprot_accession)
    if not rows:
        return None
    return _structure_response(rows, uniprot_accession)


def _fetch_tsv(accession: str) -> list[dict]:
    """Call SIGNOR getData.php and parse the TSV into a list of row dicts."""
    try:
        resp = requests.get(
            SIGNOR_BASE,
            params={"organism": "9606", "id": accession},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("SIGNOR fetch failed", extra={"accession": accession, "error": str(exc)})
        raise SignorServiceError(f"SIGNOR API unavailable: {exc}") from exc

    text = resp.text.strip()
    if not text:
        return []

    rows = []
    for line in text.split("\n"):
        parts = line.split("\t")
        if len(parts) < 22:
            continue
        while len(parts) < len(TSV_COLUMNS):
            parts.append("")
        row = dict(zip(TSV_COLUMNS, parts))
        rows.append(row)
    return rows


def _structure_response(rows: list[dict], accession: str) -> dict:
    """Transform raw TSV rows into the API response structure."""
    entity_name = _resolve_entity_name(rows, accession)
    interactions = _build_interactions(rows)
    modifications = _build_modifications(rows, accession)

    return {
        "entity_name": entity_name,
        "total_relations": len(rows),
        "interactions": interactions,
        "modifications": modifications,
    }


def _resolve_entity_name(rows: list[dict], accession: str) -> str:
    for row in rows:
        if row["id_a"] == accession:
            return row["entity_a"]
        if row["id_b"] == accession:
            return row["entity_b"]
    return accession


def _build_interactions(rows: list[dict]) -> list[dict]:
    """
    Deduplicate rows by (entity_a, entity_b, effect, mechanism) and
    aggregate PMIDs, keeping the highest score per group.
    """
    groups: dict[tuple, dict] = {}

    for row in rows:
        key = (row["entity_a"], row["entity_b"], row["effect"], row["mechanism"])
        score = _safe_float(row.get("score", ""))

        if key not in groups:
            groups[key] = {
                "entity_a": row["entity_a"],
                "type_a": row["type_a"],
                "id_a": row["id_a"],
                "entity_b": row["entity_b"],
                "type_b": row["type_b"],
                "id_b": row["id_b"],
                "effect": row["effect"],
                "mechanism": row["mechanism"],
                "score": score,
                "pmids": set(),
                "sentences": [],
                "signor_id": row["signor_id"],
            }
        else:
            groups[key]["score"] = max(groups[key]["score"], score)

        pmid = row.get("pmid", "").strip()
        if pmid and pmid not in groups[key]["pmids"]:
            groups[key]["pmids"].add(pmid)
            sentence = row.get("sentence", "").strip()
            if sentence:
                groups[key]["sentences"].append(sentence)

    result = []
    for g in groups.values():
        result.append({
            "entity_a": g["entity_a"],
            "type_a": g["type_a"],
            "id_a": g["id_a"],
            "entity_b": g["entity_b"],
            "type_b": g["type_b"],
            "id_b": g["id_b"],
            "effect": g["effect"],
            "mechanism": g["mechanism"],
            "score": round(g["score"], 3),
            "pmids": sorted(g["pmids"]),
            "sentences": g["sentences"][:3],
            "signor_id": g["signor_id"],
        })

    result.sort(key=lambda x: x["score"], reverse=True)
    return result


def _build_modifications(rows: list[dict], accession: str) -> list[dict]:
    """
    Extract unique modification sites where the queried protein is the target
    (entity_b) and residue + mechanism are present.
    """
    seen = set()
    mods = []

    for row in rows:
        if row["id_b"] != accession:
            continue
        residue = row.get("residue", "").strip()
        mechanism = row.get("mechanism", "").strip()
        if not residue or not mechanism:
            continue

        dedup_key = (row["entity_a"], residue, mechanism)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        mods.append({
            "modifier": row["entity_a"],
            "residue": residue,
            "sequence": row.get("sequence", "").strip(),
            "effect": row.get("effect", "").strip(),
            "mechanism": mechanism,
        })

    return mods


def _safe_float(val: str) -> float:
    try:
        return float(val.strip())
    except (ValueError, AttributeError):
        return 0.0
