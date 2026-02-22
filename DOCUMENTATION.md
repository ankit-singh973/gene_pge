# Gene Page Explorer – Comprehensive Project Documentation

## 1. Project Overview
The **Gene Page Explorer** is a high-performance, research-grade web application designed to provide comprehensive biological summaries for human genes. By integrating real-time data from the **UniProt Knowledgebase**, the platform normalizes complex biological information into an intuitive, interactive dashboard.

### Core Objectives
*   **Data Aggregation**: Fetching curated data (Swiss-Prot) for Homo sapiens entries.
*   **Complex Extraction**: Parsing nested biological features such as Post-Translational Modifications (PTMs) and natural variants.
*   **Scientific Visualization**: Providing interactive SVGs to map genetic variants onto protein backbones.
*   **Literature Linkage**: Directly connecting biological facts to PubMed citations.

---

## 2. System Architecture
The project follows a decoupled architecture ensuring high availability and low latency.

### Tech Stack
*   **Backend**: Python 3.10+, FastAPI (Asynchronous Framework).
*   **Data Models**: Pydantic v2 (Strict Typing & Validation).
*   **Caching**: Redis (Primary) with In-Memory fallback (Secondary).
*   **Frontend**: React 18 (SPA via CDN), Tailwind CSS (Styling), Lucide (Icons).
*   **Visualization**: Modular SVG Components & RCSB 3D Mol* Viewer Integration.

### Data Flow Execution
1.  **Request**: User enters HGNC symbol (e.g., TP53) on the Frontend.
2.  **Sanitization**: Backend validates the symbol against regex patterns.
3.  **Cache Check**: System checks Redis for existing data (TTL: 24h).
4.  **External Fetch**: If Cache Miss, the `UniProtService` queries `rest.uniprot.org`.
5.  **Normalization**: Raw UniProt JSON is parsed into the Research-Grade Schema (v2).
6.  **Response**: Frontend receives clean, structured JSON and renders components.

---

## 3. Backend Component Breakdown

### 3.1 Core Configuration (`/core/config.py`)
Centralized settings management using `pydantic-settings`. It handles:
*   UniProt Base URL & API timeouts.
*   Redis connection strings.
*   Rate limiting thresholds (Default: 30 requests/min).

### 3.2 Normalization Engine (`/services/uniprot.py`)
The heart of the application. It performs massive transformations:
*   **Reference Mapping**: Pre-builds a dictionary of Citations to allow O(1) matching for PTMs and Variants.
*   **Feature Parsing**: Iterates through UniProt `features` array to extract `Modified residue` and `Natural variant`.
*   **Cross-Reference Logic**: Maps external DB IDs to functional URLs (Bgee, HPA, ExpressionAtlas).
*   **Structure Extraction**: Resolves PDB IDs and AlphaFold DB links for 3D visualization.

### 3.3 Data Models (`/models/gene.py`)
A nested Pydantic structure that defines the API contract.
*   `IdentificationInfo`: Gene symbols, synonyms, and protein names.
*   `FunctionInfo`: General descriptions, subcellular locations, and references.
*   `ExpressionInfo`: Tissue specificity and external database bridges.
*   `PTMInfo`: Modification sites (Phosphoserine, Acetyllysine, etc.).
*   `Variant`: Position-specific mutations with clinical significance (Pathogenic, Benign).
*   `StructureInfo`: Array of PDB IDs (X-ray, NMR, Cryo-EM) with resolution data and AlphaFold predictions.

---

## 4. Frontend Component Breakdown

### 4.1 Interactive Variant Viewer (SVG)
A custom-built SVG component that renders a protein backbone scaled to the actual amino acid length.
*   **Density Mapping**: Handles 1,000+ variants (as seen in TP53) without performance degradation.
*   **Color Coding**: 
    *   <span style="color:red">●</span> **Red**: Pathogenic/Disease-linked.
    *   <span style="color:blue">●</span> **Blue**: Benign.
    *   <span style="color:gray">●</span> **Gray**: Uncertain/Uncharacterized.
*   **Detail Drawer**: Clicking a dot opens a focused UI block showing the mutation details and associated PubMed references.

### 4.2 Sticky Navigation & Scroll-Spy
A sidebar that persists as the user scrolls, highlighting the current active section (Functional, Sequence, Expression, etc.) for easy orientation in long documents.

### 4.3 Protein Structure & 3D Visualization
A dedicated module for structural biology:
*   **PDB Catalog**: Lists all experimental structures with metadata (Resolution, Methodology).
*   **Interactive 3D Box**: Embedded Mol* Viewer that loads select structures in real-time, allowing for rotation, zoom, and structural analysis.
*   **AlphaFold Integration**: Direct linkage to AlphaFold DB for computational structural predictions.

### 4.4 Reference Blocks
Collapsible sections that prevent UI clutter. They display paper titles and provide one-click access to PubMed records.

---

## 5. API Reference

### `GET /api/v1/gene/{hgnc_symbol}`
Returns the full biological summary.
*   **Parameters**: `hgnc_symbol` (string, required).
*   **Success Response (200)**: `GeneSummaryResponse` JSON.
*   **Errors**: 
    *   `400`: Invalid symbol format.
    *   `404`: Human gene not found.
    *   `503`: UniProt API failure.

### `GET /api/v1/gene/{hgnc_symbol}/exists`
Lightweight check for gene existence.
*   **Success Response (200)**: `{"exists": true/false}`.

### `GET /api/v1/gene/{hgnc_symbol}/signor`
Returns SIGNOR signaling interaction data for the given gene.
*   **Success Response (200)**: `SignorDataResponse` JSON (interactions, modifications, entity name).
*   **Errors**:
    *   `400`: Invalid symbol format.
    *   `404`: Gene not found or no SIGNOR data.
    *   `503`: SIGNOR API unavailable.

---

## 6. External Resources & Links
The project integrates data and links from the following biological repositories:

| Resource | Purpose | Link |
| :--- | :--- | :--- |
| **UniProtKB** | Primary Data Source (Curated Swiss-Prot) | [uniprot.org](https://www.uniprot.org/) |
| **PubMed** | Scientific Literature references | [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/) |
| **Bgee** | Gene Expression Evolution | [bgee.org](https://bgee.org/) |
| **HPA** | Human Protein Atlas (Expression mapping) | [proteinatlas.org](https://www.proteinatlas.org/) |
| **ExpressionAtlas**| EBI Differential Gene Expression | [ebi.ac.uk/gxa](https://www.ebi.ac.uk/gxa/) |
| **RCSB PDB** | Experimental 3D Protein Structures | [rcsb.org](https://www.rcsb.org/) |
| **AlphaFold DB** | AI-based Structure Predictions | [alphafold.ebi.ac.uk](https://alphafold.ebi.ac.uk/) |
| **SIGNOR** | Signaling Network Interactions | [signor.uniroma2.it](https://signor.uniroma2.it/) |
| **Reactome** | Biological Pathways | [reactome.org](https://reactome.org/) |

---

## 7. Setup & Installation

### Prerequisites
*   Python 3.10 or higher.
*   Redis Server (Optional, system falls back to in-memory cache if unavailable).

### Execution Steps
1.  **Clone the directory**.
2.  **Create Virtual Environment**:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```
3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run Server**:
    ```bash
    uvicorn main:app --reload
    ```
5.  **Access UI**: Navigate to `http://localhost:8000`.

---
**Document Status**: *Research-Grade Upgrade (Phase 3) Verified*  
**Last Updated**: 2026-02-22
