"""
Gene router – handles all /api/v1/gene/* endpoints.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from core.logging_config import get_logger, log_request
from core.security import sanitize_and_validate
from models.gene import ExistsResponse, ErrorResponse, GeneSummaryResponse, SignorDataResponse
from services.cache import cache_service
from services.signor import fetch_signor_data, SignorServiceError
from services.uniprot import fetch_gene_summary, gene_exists, UniProtServiceError

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/gene", tags=["Gene Summary"])


@router.get(
    "/{hgnc_symbol}",
    response_model=GeneSummaryResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid gene symbol"},
        404: {"model": ErrorResponse, "description": "Gene not found"},
        503: {"model": ErrorResponse, "description": "UniProt unavailable"},
    },
    summary="Get full gene summary",
    description="Returns structured biological information for the given HGNC gene symbol.",
)
async def get_gene_summary(hgnc_symbol: str, request: Request):
    t0 = time.perf_counter()
    symbol, error = sanitize_and_validate(hgnc_symbol)

    if error:
        return JSONResponse(status_code=400, content={"error": error})

    # ── Cache check ──────────────────────────────────────────────────────────
    cached = cache_service.get(symbol)
    if cached:
        elapsed = (time.perf_counter() - t0) * 1000
        log_request(logger, symbol, "HIT", None, elapsed)
        return JSONResponse(status_code=200, content=cached)

    # ── UniProt fetch ────────────────────────────────────────────────────────
    try:
        data = fetch_gene_summary(symbol)
    except UniProtServiceError:
        elapsed = (time.perf_counter() - t0) * 1000
        log_request(logger, symbol, "MISS", 503, elapsed, error="UniProt service unavailable")
        return JSONResponse(status_code=503, content={"error": "UniProt service unavailable"})

    if data is None:
        elapsed = (time.perf_counter() - t0) * 1000
        log_request(logger, symbol, "MISS", 200, elapsed, error="not found")
        return JSONResponse(status_code=404, content={"error": "Human gene not found in UniProt."})

    # ── Cache store & return ─────────────────────────────────────────────────
    cache_service.set(symbol, data)
    elapsed = (time.perf_counter() - t0) * 1000
    log_request(logger, symbol, "MISS", 200, elapsed)
    return JSONResponse(status_code=200, content=data)


@router.get(
    "/{hgnc_symbol}/exists",
    response_model=ExistsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid gene symbol"},
        503: {"model": ErrorResponse, "description": "UniProt unavailable"},
    },
    summary="Check gene existence",
    description="Returns whether the gene exists as a reviewed human entry in UniProt.",
)
async def check_gene_exists(hgnc_symbol: str, request: Request):
    t0 = time.perf_counter()
    symbol, error = sanitize_and_validate(hgnc_symbol)
    if error:
        return JSONResponse(status_code=400, content={"error": error})

    # Check cache first
    cached = cache_service.get(symbol)
    if cached is not None:
        elapsed = (time.perf_counter() - t0) * 1000
        log_request(logger, symbol, "HIT", None, elapsed)
        return {"exists": True}

    try:
        exists = gene_exists(symbol)
    except UniProtServiceError:
        elapsed = (time.perf_counter() - t0) * 1000
        log_request(logger, symbol, "MISS", 503, elapsed, error="UniProt unavailable")
        return JSONResponse(status_code=503, content={"error": "UniProt service unavailable"})

    elapsed = (time.perf_counter() - t0) * 1000
    log_request(logger, symbol, "MISS", 200, elapsed)
    return {"exists": exists}


SIGNOR_CACHE_PREFIX = "signor_v1:"


@router.get(
    "/{hgnc_symbol}/signor",
    response_model=SignorDataResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid gene symbol"},
        404: {"model": ErrorResponse, "description": "Gene not found or no SIGNOR data"},
        503: {"model": ErrorResponse, "description": "SIGNOR API unavailable"},
    },
    summary="Get SIGNOR interaction data",
    description="Returns signaling interaction data from the SIGNOR database for the given gene.",
)
async def get_signor_data(hgnc_symbol: str, request: Request):
    t0 = time.perf_counter()
    symbol, error = sanitize_and_validate(hgnc_symbol)
    if error:
        return JSONResponse(status_code=400, content={"error": error})

    # ── SIGNOR cache check ───────────────────────────────────────────────────
    signor_key = f"{SIGNOR_CACHE_PREFIX}{symbol}"
    cached = cache_service.get_raw(signor_key)
    if cached:
        elapsed = (time.perf_counter() - t0) * 1000
        log_request(logger, symbol, "HIT", None, elapsed)
        return JSONResponse(status_code=200, content=cached)

    # ── Resolve UniProt accession ────────────────────────────────────────────
    gene_data = cache_service.get(symbol)
    if not gene_data:
        try:
            gene_data = fetch_gene_summary(symbol)
        except UniProtServiceError:
            pass

    if not gene_data or not gene_data.get("uniprot_accession"):
        elapsed = (time.perf_counter() - t0) * 1000
        log_request(logger, symbol, "MISS", 404, elapsed, error="gene not found")
        return JSONResponse(status_code=404, content={"error": "Gene not found in UniProt."})

    accession = gene_data["uniprot_accession"]

    # ── SIGNOR fetch ─────────────────────────────────────────────────────────
    try:
        data = fetch_signor_data(accession)
    except SignorServiceError:
        elapsed = (time.perf_counter() - t0) * 1000
        log_request(logger, symbol, "MISS", 503, elapsed, error="SIGNOR unavailable")
        return JSONResponse(status_code=503, content={"error": "SIGNOR service unavailable"})

    if data is None:
        elapsed = (time.perf_counter() - t0) * 1000
        log_request(logger, symbol, "MISS", 404, elapsed, error="no SIGNOR data")
        return JSONResponse(
            status_code=200,
            content={"interactions": [], "modifications": [], "entity_name": "", "total_relations": 0},
        )

    # ── Cache & return ───────────────────────────────────────────────────────
    cache_service.set_raw(signor_key, data)
    elapsed = (time.perf_counter() - t0) * 1000
    log_request(logger, symbol, "MISS", 200, elapsed)
    return JSONResponse(status_code=200, content=data)
