from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class PubMedReference(BaseModel):
    pubmed_id: str = ""
    title: str = ""
    url: str = ""


class IdentificationInfo(BaseModel):
    primary_gene: str = ""
    synonyms: List[str] = Field(default_factory=list)
    alternative_protein_names: List[str] = Field(default_factory=list)
    length: int = 0


class FunctionSubSection(BaseModel):
    title: str = ""
    content: str = ""


class FunctionInfo(BaseModel):
    general_function: str = ""
    subsections: List[FunctionSubSection] = Field(default_factory=list)
    references: List[PubMedReference] = Field(default_factory=list)


class ExternalLink(BaseModel):
    database: str = ""
    url: str = ""


class ExpressionInfo(BaseModel):
    tissue_specificity: str = ""
    developmental_stage: str = ""
    induction: str = ""
    external_links: List[ExternalLink] = Field(default_factory=list)


class PTMSite(BaseModel):
    position: int = 0
    residue: str = ""
    type: str = ""
    references: List[PubMedReference] = Field(default_factory=list)


class PTMInfo(BaseModel):
    description: str = ""
    sites: List[PTMSite] = Field(default_factory=list)
    external_links: List[ExternalLink] = Field(default_factory=list)


class Variant(BaseModel):
    position: int = 0
    original_residue: str = Field(alias="from", default="")
    variant_residue: str = Field(alias="to", default="")
    description: str = ""
    disease: str = ""
    clinical_significance: str = ""
    references: List[PubMedReference] = Field(default_factory=list)
    clinvar_id: str = ""
    dbsnp_id: str = ""

    class Config:
        populate_by_name = True


class SequenceInfo(BaseModel):
    length: int = 0
    sequence: str = ""


class PDBStructure(BaseModel):
    pdb_id: str = ""
    method: str = ""
    resolution: str = ""
    link: str = ""


class StructureInfo(BaseModel):
    pdb_structures: List[PDBStructure] = Field(default_factory=list)
    alphafold_link: str = ""


class ReactomePathway(BaseModel):
    pathway_id: str = ""
    pathway_name: str = ""
    url: str = ""


class SignorLink(BaseModel):
    signor_id: str = ""
    url: str = ""


class SignorInteraction(BaseModel):
    entity_a: str = ""
    type_a: str = ""
    id_a: str = ""
    entity_b: str = ""
    type_b: str = ""
    id_b: str = ""
    effect: str = ""
    mechanism: str = ""
    score: float = 0.0
    pmids: List[str] = Field(default_factory=list)
    sentences: List[str] = Field(default_factory=list)
    signor_id: str = ""


class SignorModification(BaseModel):
    modifier: str = ""
    residue: str = ""
    sequence: str = ""
    effect: str = ""
    mechanism: str = ""


class SignorDataResponse(BaseModel):
    interactions: List[SignorInteraction] = Field(default_factory=list)
    modifications: List[SignorModification] = Field(default_factory=list)
    entity_name: str = ""
    total_relations: int = 0


class GeneSummaryResponse(BaseModel):
    gene_symbol: str = ""
    uniprot_accession: str = ""
    entry_status: str = ""
    annotation_score: str = ""
    organism: str = "Homo sapiens"
    identification: IdentificationInfo = Field(default_factory=IdentificationInfo)
    function: FunctionInfo = Field(default_factory=FunctionInfo)
    expression: ExpressionInfo = Field(default_factory=ExpressionInfo)
    ptm: PTMInfo = Field(default_factory=PTMInfo)
    variants: List[Variant] = Field(default_factory=list)
    sequence: SequenceInfo = Field(default_factory=SequenceInfo)
    structure: StructureInfo = Field(default_factory=StructureInfo)
    reactome: List[ReactomePathway] = Field(default_factory=list)
    signor: List[SignorLink] = Field(default_factory=list)


class ExistsResponse(BaseModel):
    exists: bool


class ErrorResponse(BaseModel):
    error: str
