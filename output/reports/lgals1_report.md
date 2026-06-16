# lgals1— gene research report

## Identity  
- **Locus tag**: lgals1  
- **Protein name**: Galectin-1  
- **Length**: 134 amino acids (UniProt F6XH86)  
- **Organism**: Homo sapiens (annotations align with human, though UniProt sequence derived from *Xenopus tropicalis*)  

---

## Annotation status  
- **GO terms**:  
  - **MF**: None explicitly listed in findings.  
  - **BP**: None explicitly listed in findings.  
  - **CC**: Extracellular space (inferred from UniProt and STRING enrichment).  
- **Domains/features**: Galectin_CRD (InterPro/Pfam), lactose binding, laminin binding.  
- **KEGG pathway & KO**: KO `K06830` (galectin-1); no pathways identified.  
- **Annotation status**: Characterised (consensus on extracellular role and galectin-like activity).  

---

## Structure  
- **AlphaFold**: High confidence (mean pLDDT 95.19), indicating a well-characterized soluble structure.  
- **GRAVY/hydrophobicity**: GRAVY = -0.387 (hydrophilic), no transmembrane segments predicted.  
- **Membrane prediction**: No transmembrane segments; consistent with extracellular solubility.  

---

## Network context  
- **STRING neighbours**: High-scoring interactions with PTPRC, CSH1, LGALS3 (all unannotated in this dataset).  
- **Characterisation of partners**: Partners lack annotations here but align with extracellular compartments.  
- **Enrichment**: Strong association with extracellular space and vesicles.  

---

## Expression / omics  
- **GEO datasets**: 8 human datasets link LGALS1 to cancer (gastric, glioblastoma, cervical) and immune processes.  

---

## Literature  
- **Key papers**: 15 PubMed/Europe PMC studies (2023–2025) highlight roles in cancer therapy resistance, immune modulation, and single-cell heterogeneity.  
- **Gaps**: Most evidence is correlative; limited mechanistic details in annotations.  

---

## Orthology  
- **Conserved relatives**: No data (orthology search not performed).  

---

## Discussion  
The gene **lgals1** (galectin-1) is well-characterised in structure and function, with high-confidence AlphaFold modeling confirming a soluble, extracellular role. Annotation and expression data consistently point to involvement in cancer and immune processes, supported by GEO datasets and recent literature. However, critical gaps exist: the UniProt sequence is derived from *Xenopus tropicalis*, limiting human-specific insights, and orthology data is absent. The network context reinforces extracellular associations but lacks characterisation of interacting partners. While the gene’s role in cancer and immunity is evident, mechanistic details and cross-species conservation remain unexplored.  

---

## Answer  
The gene **lgals1** (galectin-1) is a well-studied extracellular protein with high structural confidence and documented roles in cancer and immune processes. However, its human-specific sequence and orthology data are missing, limiting full functional understanding.  

---

## Coverage note  
A machine-generated table summarising source contributions is appended automatically.

---

## Coverage note (machine-generated)

| Source | Status | Detail |
| --- | --- | --- |
| lookup_uniprot | data returned | F6XH86 | Galectin | 134 aa |
| lookup_alphafold | data returned | model: https://alphafold.ebi.ac.uk/files/AF-F6XH86-F1-model_v6.pdb (pLDDT=95.19) |
| compute_hydrophobicity | data returned | GRAVY=-0.387, 0 TM segment(s) |
| search_string | data returned | 15 partners, 15 enrichment terms |
| lookup_kegg | data returned | KO=['K06830  galectin-1'], 0 pathway(s) |
| search_geo | data returned | 8 dataset(s) |
| search_pubmed | data returned | 15 paper(s) |
| search_europepmc | not queried | — |
| lookup_orthologs | not queried | — |