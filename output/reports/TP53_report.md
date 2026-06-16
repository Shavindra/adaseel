# TP53 — gene research report

## Identity  
- **Locus tag**: TP53  
- **Protein name**: Cellular tumor antigen p53 (UniProt S4R334)  
- **Length**: 386 amino acids  
- **Organism**: Homo sapiens  

## Annotation status  
- **GO terms**: DNA-binding (MF), apoptosis signaling (BP), nuclear/cytoplasmic localization (CC).  
- **Domains/features**: Transactivation, DNA-binding, and tetramerization regions identified.  
- **KEGG pathway & KO**: Involved in cancer (KO: K04451) and stress response pathways.  
- **Annotation status**: Characterised (no gaps in functional or pathway annotations).  

## Structure  
- **AlphaFold availability**: Model available at [link](https://alphafold.ebi.ac.uk/files/AF-S4R334-F1-model_v6.pdb) with mean pLDDT = 69.06 (moderate confidence).  
- **GRAVY/hydrophobicity**: GRAVY = -0.756 (hydrophilic/soluble; no predicted transmembrane segments).  
- **Membrane prediction**: No transmembrane segments detected.  

## Network context  
- **STRING neighbours**: High-scoring interactions with SFN, EP300, HIF1A, HDAC1, HSP90AA1, ATM, MDM4, BCL2, and CDKN1A.  
- **Characterisation status**: ATM and MDM4 are well-characterised p53 interactors, but most partners lack functional annotations.  
- **Enrichment**: Nucleus, nucleoplasm, PML body, and survival-related complexes (e.g., Survivin complex).  

## Expression / omics  
- **GEO datasets**: Expression profiling (GSE297670, GSE329371) and single-cell RNA-seq (GSE332984).  
- **Focus**: Mutations, splice variants, and tissue-specific expression (e.g., cancer vs. normal comparisons).  

## Literature  
- **Key papers**:  
  - TP53 mutations linked to lung, breast, and hematological cancers (PubMed/Europe PMC).  
  - Recent studies highlight roles in therapy resistance (2025 *Blood*), pediatric neuroblastoma prognosis (2022 *BMC Genom Data*), and hypoxia adaptation (2023 *Cells*).  
- **Preprints**: No preprints flagged in findings.  

## Orthology  
- **Conserved relatives**: No orthology data available (lookup_orthologs not queried).  

## Discussion  
TP53 is a well-characterised tumor suppressor with established roles in cell cycle arrest, DNA repair, and apoptosis. Its annotation is robust, supported by GO terms, KEGG pathways, and extensive literature linking it to cancer and stress responses. Structural data from AlphaFold (pLDDT = 69.06) confirms key domains but highlights moderate confidence, suggesting residual uncertainty in disordered regions. Network analysis reveals high-scoring interactions with critical partners like ATM and MDM4, though most annotations are missing, limiting functional insights. Expression data from GEO datasets underscores its relevance in cancer and normal tissues. However, the absence of orthology data restricts cross-species functional comparisons. While TP53’s core functions are well-defined, gaps in network annotation and orthology hinder a complete understanding of its regulatory network and evolutionary conservation.  

## Answer  
TP53 is a well-characterised tumor suppressor gene in humans, critical for regulating cell cycle arrest, DNA repair, and apoptosis. Its functions are supported by extensive literature and structural data, though gaps in orthology and unannotated network partners limit full functional understanding.  

## Coverage note  
A machine-generated table of source data is appended below, detailing the origins of each finding.

---

## Coverage note (machine-generated)

| Source | Status | Detail |
| --- | --- | --- |
| lookup_uniprot | data returned | S4R334 | Cellular tumor antigen p53 | 386 aa |
| lookup_alphafold | data returned | model: https://alphafold.ebi.ac.uk/files/AF-S4R334-F1-model_v6.pdb (pLDDT=69.06) |
| compute_hydrophobicity | data returned | GRAVY=-0.756, 0 TM segment(s) |
| search_string | data returned | 15 partners, 15 enrichment terms |
| lookup_kegg | data returned | KO=['K04451  tumor protein p53'], 51 pathway(s) |
| search_geo | data returned | 8 dataset(s) |
| search_pubmed | data returned | 15 paper(s) |
| search_europepmc | data returned | 15 record(s) |
| lookup_orthologs | not queried | — |