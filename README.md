# Gene Page Explorer

A research-grade, single-page web application for exploring human gene data. Integrates curated biological data from UniProt Swiss-Prot, SIGNOR signaling networks, Reactome pathways, and PDB/AlphaFold protein structures into one cohesive dashboard.

## Features

- **Gene Summary** — Function, expression, sequence, and identification from UniProt Swiss-Prot (Homo sapiens only)
- **Variant Viewer** — Interactive SVG-based mapping of genetic variants with clinical significance filtering
- **Post-Translational Modifications** — Collapsible table of modification sites with PubMed evidence
- **Reactome Pathways** — Annotated pathway cards with direct links
- **SIGNOR Signaling Network** — Interactive Cytoscape.js graph with:
  - Relation type filters (Activates / Inhibits / Complex / Other)
  - Score cutoff slider
  - Fullscreen modal
  - Click-to-inspect nodes and edges with evidence detail
- **3D Structure** — Mol* viewer for PDB structures and AlphaFold predictions
- **Literature** — Direct PubMed linkage throughout

## Tech Stack

| Layer | Technology |
|:------|:-----------|
| Backend | Python 3, FastAPI, Pydantic v2, Uvicorn |
| Frontend | React 18 (CDN), Tailwind CSS (CDN), Cytoscape.js, Lucide Icons |
| Caching | Redis (with in-memory fallback) |
| Data Sources | UniProt REST API, SIGNOR REST API, PDB, AlphaFold, Reactome |

## Project Structure

```
gene_page/
├── core/
│   ├── config.py            # App settings (Redis, UniProt, rate limits)
│   ├── logging_config.py    # Structured logging
│   └── security.py          # HGNC symbol validation
├── models/
│   └── gene.py              # Pydantic response models
├── routers/
│   └── gene.py              # API route handlers
├── services/
│   ├── cache.py             # Redis / in-memory cache
│   ├── signor.py            # SIGNOR API integration
│   └── uniprot.py           # UniProt data extraction
├── frontend/
│   └── index.html           # Single-page React application
├── main.py                  # FastAPI entry point
├── requirements.txt         # Python dependencies
├── DOCUMENTATION.md         # Detailed technical documentation
└── .gitignore
```

## API Endpoints

| Endpoint | Description |
|:---------|:------------|
| `GET /api/v1/gene/{symbol}` | Full gene summary (variants, PTMs, pathways, structure) |
| `GET /api/v1/gene/{symbol}/exists` | Lightweight existence check |
| `GET /api/v1/gene/{symbol}/signor` | SIGNOR signaling interaction data |
| `GET /health` | Health check |
| `GET /docs` | Swagger API documentation |

## Setup

```bash
# Clone
git clone https://github.com/ankit-singh973/gene_pge.git
cd gene_pge

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload

# Open in browser
# http://localhost:8000
```

Optional: start Redis for persistent caching (falls back to in-memory if unavailable).

## Data Sources

| Source | Usage |
|:-------|:------|
| [UniProt Swiss-Prot](https://www.uniprot.org) | Gene function, variants, PTMs, expression, sequence |
| [SIGNOR](https://signor.uniroma2.it) | Protein signaling interactions |
| [Reactome](https://reactome.org) | Biological pathways |
| [PDB](https://www.rcsb.org) | Experimental protein structures |
| [AlphaFold](https://alphafold.ebi.ac.uk) | Predicted protein structures |
