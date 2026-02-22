"""
UniProt REST API integration service.

Flow:
  1. Build query: gene_exact:<SYMBOL> AND organism_id:9606 AND reviewed:true
  2. Fetch with timeout=10s and up to 2 retries
  3. Filter: organism_id must be 9606, entryType must be "UniProtKB reviewed (Swiss-Prot)"
  4. Select best entry (highest annotation score if multiple)
  5. Normalize into GeneSummaryResponse dict
"""
from __future__ import annotations

import re
import time
from typing import Any, Optional

import requests

from core.config import get_settings
from core.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Fields requested from UniProt
UNIPROT_FIELDS = ",".join([
    "accession",
    "id",
    "protein_name",
    "gene_names",
    "organism_name",
    "organism_id",
    "length",
    "sequence",
    "annotation_score",
    "cc_function",
    "cc_subcellular_location",
    "cc_tissue_specificity",
    "cc_developmental_stage",
    "cc_induction",
    "cc_ptm",
    "ft_mod_res",
    "ft_variant",
    "xref_pdb",
    "xref_interpro",
    "xref_pfam",
    "references",
])

SWISS_PROT_TYPE = "UniProtKB reviewed (Swiss-Prot)"


# ────────────────────────────────────────────────────────────────────────────
# Public interface
# ────────────────────────────────────────────────────────────────────────────

def fetch_gene_summary(gene_symbol: str) -> Optional[dict]:
    """
    Query UniProt for the canonical human Swiss-Prot entry.
    Returns a normalised dict or None if not found / unavailable.
    Raises UniProtError on service failure.
    """
    raw = _query_uniprot(gene_symbol)
    if raw is None:
        return None

    results = raw.get("results", [])

    # ── Step 1: Human-only filter
    human_entries = [
        r for r in results
        if r.get("organism", {}).get("taxonId") == settings.human_organism_id
    ]
    if not human_entries:
        return None

    # ── Step 2: Prefer Swiss-Prot reviewed
    reviewed = [
        r for r in human_entries
        if r.get("entryType") == SWISS_PROT_TYPE
    ]
    candidates = reviewed if reviewed else []

    if not candidates:
        return None

    # ── Step 3: Highest annotation score wins
    best = max(candidates, key=lambda r: r.get("annotationScore", 0))
    return _normalize(gene_symbol, best)


def gene_exists(gene_symbol: str) -> bool:
    """Light-weight existence check: returns True if canonical human entry exists."""
    return fetch_gene_summary(gene_symbol) is not None


# ────────────────────────────────────────────────────────────────────────────
# UniProt HTTP call
# ────────────────────────────────────────────────────────────────────────────

def _query_uniprot(gene_symbol: str) -> Optional[dict]:
    query = f"gene_exact:{gene_symbol} AND organism_id:{settings.human_organism_id} AND reviewed:true"
    params = {
        "query": query,
        "format": "json",
        "size": 5,
    }

    last_exc: Exception | None = None
    for attempt in range(1, settings.uniprot_retries + 1):
        try:
            response = requests.get(
                settings.uniprot_base_url,
                params=params,
                timeout=settings.uniprot_timeout,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            logger.warning("UniProt timeout", extra={"gene": gene_symbol, "attempt": attempt, "error": str(exc)})
            last_exc = exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response else None
            # Log the specific response text from UniProt for debugging
            response_text = exc.response.text if exc.response else "No body"
            logger.error("UniProt HTTP error", extra={"gene": gene_symbol, "status": status, "error": response_text})
            
            if status == 404:
                return None
            raise UniProtServiceError(f"UniProt service error ({status}): {response_text[:100]}") from exc
        except requests.RequestException as exc:
            logger.error("UniProt request failed", extra={"gene": gene_symbol, "attempt": attempt, "error": str(exc)})
            last_exc = exc

    raise UniProtServiceError("UniProt service unavailable") from last_exc


# ────────────────────────────────────────────────────────────────────────────
# Normalisation Engine (Phase 3)
# ────────────────────────────────────────────────────────────────────────────

def _normalize(gene_symbol: str, entry: dict) -> dict:
    acc = entry.get("primaryAccession", "")
    
    # Pre-parse citations for performance
    ref_map = _build_reference_map(entry)

    return {
        "gene_symbol": gene_symbol.upper(),
        "uniprot_accession": acc,
        "entry_status": entry.get("entryType", ""),
        "annotation_score": str(entry.get("annotationScore", "")),
        "organism": _safe_path(entry, "organism", "scientificName") or "Homo sapiens",
        
        "identification": _extract_identification(entry),
        "function": _extract_function(entry, ref_map),
        "expression": _extract_expression(entry),
        "ptm": _extract_ptm(entry, ref_map),
        "variants": _extract_variants(entry, ref_map),
        "structure": _extract_structure(entry),
        "sequence": {
            "length": entry.get("sequence", {}).get("length", 0),
            "sequence": entry.get("sequence", {}).get("value", "")
        },
        "reactome": _extract_reactome(entry),
        "signor": _extract_signor(entry)
    }


def _build_reference_map(entry: dict) -> dict:
    """Maps referenceNumber and pubmed_id to parsed citation data."""
    ref_map = {"by_num": {}, "by_id": {}}
    refs = entry.get("references", [])
    for ref in refs:
        cid = ref.get("referenceNumber")
        citation = ref.get("citation", {})
        pub_id = ""
        for x in citation.get("citationCrossReferences", []):
            if x.get("database") == "PubMed":
                pub_id = x.get("id", "")
                break
        
        info = {
            "pubmed_id": pub_id,
            "title": citation.get("title", "No title available"),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pub_id}/" if pub_id else ""
        }
        if cid:
            ref_map["by_num"][cid] = info
        if pub_id:
            ref_map["by_id"][pub_id] = info
    return ref_map


def _map_evidences(evidences: list, ref_map: dict) -> list[dict]:
    """Extracts unique PubMed references from a list of UniProt evidence tags."""
    mapped = []
    seen = set()
    if not isinstance(evidences, list):
        return []

    for ev in evidences:
        if not isinstance(ev, dict):
            continue
            
        source = ev.get("source")
        ref = None
        
        if isinstance(source, dict):
            ref_id = source.get("referenceNumber")
            ref = ref_map["by_num"].get(ref_id)
        elif isinstance(source, str) and source == "PubMed":
            pub_id = ev.get("id")
            # Try to find in our pre-built map to get the title
            ref = ref_map["by_id"].get(pub_id)
            if not ref and pub_id:
                ref = {
                    "pubmed_id": pub_id,
                    "title": f"PubMed Record {pub_id}",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pub_id}/"
                }
        
        if ref and ref.get("pubmed_id") and ref["pubmed_id"] not in seen:
            mapped.append(ref)
            seen.add(ref["pubmed_id"])
    return mapped


def _extract_identification(entry: dict) -> dict:
    prot = entry.get("proteinDescription", {})
    rec = prot.get("recommendedName", {})
    
    alt_names = []
    for alt in prot.get("alternativeNames", []):
        v = _get_value(alt.get("fullName", {}))
        if v: alt_names.append(v)

    genes = entry.get("genes", [])
    primary = ""
    synonyms = []
    for g in genes:
        if not primary:
            primary = _get_value(g.get("geneName", {}))
        for syn in g.get("synonyms", []):
            v = _get_value(syn)
            if v: synonyms.append(v)

    return {
        "primary_gene": primary,
        "synonyms": synonyms,
        "alternative_protein_names": alt_names,
        "length": entry.get("sequence", {}).get("length", 0)
    }


def _extract_function(entry: dict, ref_map: dict) -> dict:
    comments = entry.get("comments", [])
    general = ""
    subsections = []
    refs = []
    all_locations = []
    seen_notes = set()

    for c in comments:
        ctype = c.get("commentType", "")
        if ctype == "FUNCTION":
            texts = c.get("texts", [])
            for t in texts:
                val = t.get("value", "")
                if val:
                    cleaned_val = _clean_text(val)
                    if not general: 
                        general = cleaned_val
                    elif cleaned_val not in seen_notes:
                        subsections.append({"title": "Note", "content": cleaned_val})
                        seen_notes.add(cleaned_val)
                # Extract refs linked to this function
                refs.extend(_map_evidences(t.get("evidences", []), ref_map))
        
        elif ctype == "SUBCELLULAR LOCATION":
            for loc in c.get("subcellularLocations", []):
                v = _get_value(loc.get("location", {}))
                if v and v not in all_locations: 
                    all_locations.append(v)

    if all_locations:
        subsections.append({
            "title": "Subcellular Location", 
            "content": ", ".join(all_locations)
        })

    # Deduplicate refs
    unique_refs = {r["pubmed_id"]: r for r in refs if r["pubmed_id"]}.values()

    return {
        "general_function": general,
        "subsections": subsections,
        "references": list(unique_refs)
    }


def _extract_expression(entry: dict) -> dict:
    comments = entry.get("comments", [])
    tissue = ""
    dev = ""
    induc = ""
    
    for c in comments:
        ctype = c.get("commentType", "")
        vals = [t.get("value", "") for t in c.get("texts", []) if t.get("value")]
        if not vals: continue
        
        if ctype == "TISSUE SPECIFICITY": tissue = _clean_text(vals[0])
        elif ctype == "DEVELOPMENTAL STAGE": dev = _clean_text(vals[0])
        elif ctype == "INDUCTION": induc = _clean_text(vals[0])

    # External Links - Exclude ProteomicsDB as requested
    links = []
    db_map = {
        "Bgee": "https://bgee.org/?page=gene&gene_id=",
        "HPA": "https://www.proteinatlas.org/",
        "ExpressionAtlas": "https://www.ebi.ac.uk/gxa/genes/"
    }
    
    for xref in entry.get("uniProtKBCrossReferences", []):
        db = xref.get("database", "")
        xid = xref.get("id", "")
        if db in db_map:
            url = db_map[db] + xid if db != "HPA" else f"https://www.proteinatlas.org/{xid}"
            links.append({"database": db, "url": url})

    return {
        "tissue_specificity": tissue,
        "developmental_stage": dev,
        "induction": induc,
        "external_links": links
    }


def _extract_ptm(entry: dict, ref_map: dict) -> dict:
    desc = ""
    for c in entry.get("comments", []):
        if c.get("commentType") == "PTM":
            desc = " ".join([_clean_text(t.get("value", "")) for t in c.get("texts", []) if t.get("value")])
            break
    
    sites = []
    for f in entry.get("features", []):
        if f.get("type") == "Modified residue":
            sites.append({
                "position": f.get("location", {}).get("start", {}).get("value", 0),
                "residue": f.get("description", "").split(";")[0], # e.g. "Phosphoserine"
                "type": f.get("description", ""),
                "references": _map_evidences(f.get("evidences", []), ref_map)
            })
    
    return {
        "description": desc,
        "sites": sorted(sites, key=lambda x: x["position"]),
        "external_links": []
    }


def _extract_variants(entry: dict, ref_map: dict) -> list[dict]:
    variants = []
    for f in entry.get("features", []):
        if f.get("type") != "Natural variant": continue
        
        pos = f.get("location", {}).get("start", {}).get("value", 0)
        desc = f.get("description", "")
        
        # Parse ClinVar/dbSNP from xrefs in feature if present
        cv_id = ""
        ds_id = ""
        # In modern UniProt JSON, variant xrefs are sometimes inside the feature
        # but often we need to check the global xrefs for ClinVar/dbSNP mappings
        
        v_ref = _map_evidences(f.get("evidences", []), ref_map)
        
        variants.append({
            "position": pos,
            "from": f.get("alternativeSequence", {}).get("originalSequence", ""),
            "to": f.get("alternativeSequence", {}).get("alternativeSequences", [""])[0],
            "description": desc,
            "disease": desc.split("(in")[0].strip() if "(in" in desc else "",
            "clinical_significance": "Disease" if "pathogenic" in desc.lower() or "disease" in desc.lower() else "Unknown",
            "references": v_ref,
            "clinvar_id": cv_id,
            "dbsnp_id": ds_id
        })
    
    return sorted(variants, key=lambda x: x["position"])


def _extract_structure(entry: dict) -> dict:
    pdb_list = []
    af_link = ""
    acc = entry.get("primaryAccession", "")
    
    if acc:
        af_link = f"https://alphafold.ebi.ac.uk/entry/{acc}"

    for xref in entry.get("uniProtKBCrossReferences", []):
        if xref.get("database") == "PDB":
            method = ""
            res_str = ""
            for p in xref.get("properties", []):
                key = p.get("key")
                val = p.get("value")
                if key == "Method": method = val
                elif key == "Resolution": res_str = val

            pid = xref.get("id", "")
            
            # Parse resolution for sorting
            res_val = float('inf') # Default for N/A or unparseable
            if res_str and res_str != "N/A":
                try:
                    # Assuming resolution is like "2.5 A"
                    res_val = float(res_str.split(' ')[0])
                except ValueError:
                    pass # Keep as inf if parsing fails

            pdb_list.append({
                "pdb_id": pid,
                "method": method or "X-ray",
                "resolution": res_str or "N/A",
                "link": f"https://www.rcsb.org/structure/{pid}",
                "_resolution_sort_val": res_val # Internal key for sorting
            })
    
    # Sort PDB structures by resolution (lower is better)
    sorted_pdb_list = sorted(pdb_list, key=lambda x: x["_resolution_sort_val"])
    # Remove the internal sorting key before returning
    for item in sorted_pdb_list:
        del item["_resolution_sort_val"]

    return {
        "pdb_structures": sorted_pdb_list,
        "alphafold_link": af_link
    }


def _extract_reactome(entry: dict) -> list[dict]:
    reactome_list = []
    for xref in entry.get("uniProtKBCrossReferences", []):
        if xref.get("database") == "Reactome":
            pathway_id = xref.get("id", "")
            pathway_name = ""
            for p in xref.get("properties", []):
                if p.get("key") == "PathwayName":
                    pathway_name = p.get("value", "")
                    break
            
            reactome_list.append({
                "pathway_id": pathway_id,
                "pathway_name": _clean_text(pathway_name),
                "url": f"https://reactome.org/PathwayBrowser/#/{pathway_id}"
            })
    return reactome_list


def _extract_signor(entry: dict) -> list[dict]:
    signor_list = []
    for xref in entry.get("uniProtKBCrossReferences", []):
        if xref.get("database") == "SIGNOR":
            signor_id = xref.get("id", "")
            if signor_id:
                signor_list.append({
                    "signor_id": signor_id,
                    "url": f"https://signor.uniroma2.it/relation_result.php?id={signor_id}"
                })
    return signor_list


def _clean_text(text: str) -> str:
    """Removes UniProt evidence tags like (PubMed:123), {ECO:123}, etc."""
    if not text: return ""
    # Remove (PubMed:123, PubMed:456) or (PubMed:123)
    text = re.sub(r'\s*\(PubMed:[^)]+\)', '', text)
    # Remove {ECO:0000269|PubMed:1234567} or {ECO:0000305}
    text = re.sub(r'\s*\{ECO:[^}]+\}', '', text)
    # Remove [PubMed:1234567]
    text = re.sub(r'\s*\[PubMed:[^\]]+\]', '', text)
    # Remove (ECO:0000269)
    text = re.sub(r'\s*\(ECO:[^)]+\)', '', text)
    # Clean up double spaces
    return re.sub(r'\s\s+', ' ', text).strip()


# ── Utility ──────────────────────────────────────────────────────────────────
def _get_value(obj: Any, key: str = "value") -> str:
    if isinstance(obj, dict): return obj.get(key, "")
    return ""

def _safe_path(obj: dict, *keys: str) -> Any:
    for k in keys:
        if not isinstance(obj, dict): return None
        obj = obj.get(k)
    return obj

class UniProtServiceError(Exception):
    pass
