# Elaborative Technical Description: Local NCBI BLAST+ Web Server

## 1. Executive Overview & Problem Statement

The **Basic Local Alignment Search Tool (BLAST)** is the cornerstone heuristic algorithm in computational biology and bioinformatics. It is utilized to compare biological query sequences (nucleotides or amino acids) against comprehensive reference libraries of known sequence data. 

While the official web portal provided by the National Center for Biotechnology Information (NCBI) is suitable for basic exploration, real-world industry labs, biotechnology firms, and clinical research teams require **local BLAST servers** for fundamental operational reasons:
1. **Confidentiality & Intellectual Property**: Proprietary therapeutic sequences, novel synthetic constructs, and patient-derived sequencing data must never be uploaded to external public clouds or web endpoints.
2. **Deterministic Latency & High Throughput**: The NCBI public web API imposes strict query throttling (rate limits, queue prioritization, and request size caps). A local cluster or server runs batch alignments with predictable, sub-second execution times.
3. **Reproducibility with Fixed Database Snapshots**: NCBI's public databases are updated continuously. Scientific benchmarks, clinical diagnostic pipelines, and peer-reviewed studies require fixed, version-locked database versions to ensure exact reproducibility across time.
4. **Offline and Isolated Deployment**: Local BLAST servers operate within secured intranets or air-gapped laboratory networks without external internet access.

This project delivers a **production-grade, secure, local BLAST web application** built using **Flask**, **BioPython**, and **NCBI BLAST+ 2.16.0** inside a Linux containerized/WSL2 architecture.

---

## 2. What We Are Doing

We have built an end-to-end bioinformatics platform that abstracts complex command-line BLAST operations into a modern, responsive web application. The platform provides:

- **Dual-Input Modalities**: Researchers can either paste raw sequence strings / FASTA blocks directly into a text area or upload `.fasta`, `.fa`, or `.txt` files (with a 2 MB upload guardrail).
- **Multi-Program Alignment Engine**:
  - `blastp`: Compares an amino acid protein query directly against a protein database.
  - `blastn`: Compares a nucleotide query (DNA/RNA) against a nucleotide database.
  - `blastx`: Automatically translates a nucleotide query in all six reading frames and compares it against a protein database.
  - `tblastn`: Compares a protein query against a nucleotide database translated dynamically in all six reading frames.
  - `tblastx`: Translates both nucleotide query and nucleotide database in all six reading frames before alignment.
- **Biologically Validated Heuristic Tuning**:
  - Expectation value threshold ($E$-value cutoffs from $10.0$ down to $10^{-50}$).
  - Maximum target hits ($1$ to $500$).
  - Scoring matrix selection (`BLOSUM62`, `BLOSUM80`, `BLOSUM45`, `PAM30`, `PAM70`).
  - Word size tuning ($2$ or $3$ for protein; $11$ to $28$ for nucleotide).
  - Minimum percent identity cutoff (`-perc_identity`).
  - Query coverage cutoff per HSP (`-qcov_hsp_perc`).
- **Comprehensive Output & Visualization**:
  - Tabular overview with hit identifier, accession, definition, query coverage percentage, sequence identity percentage, $E$-value, and bit score.
  - Formatted 60-character pairwise alignment blocks matching standard NCBI BLAST formatting.
  - Multi-format exports: Tabular TSV/CSV, structured NCBI XML, machine-readable JSON, and clean FASTA.
- **Asynchronous Processing Engine**:
  - Non-blocking background worker threads for resource-intensive searches, complete with a live-polling status page (`/job/<job_id>`).

---

## 3. Where We Are Getting the Data (Data Lineage & Provenance)

All databases used in this assignment originate from official, authoritative biological repositories and were downloaded using NCBI's pre-formatted distribution protocol.

```
+-----------------------------------------------------------------------------------+
|                            NCBI FTP Master Repository                             |
|                        ftp.ncbi.nlm.nih.gov/blast/db/                             |
+-----------------------------------------------------------------------------------+
                                        |
               +------------------------+------------------------+
               | (FTP/HTTP Sync via update_blastdb.pl)           |
               v                                                 v
  +------------------------------------+   +------------------------------------+
  |      pdbaa (Protein Database)      |   | 16S_ribosomal_RNA (Nucleotide DB)  |
  +------------------------------------+   +------------------------------------+
  | - Source: Worldwide Protein Data   |   | - Source: NCBI RefSeq Targeted     |
  |   Bank (wwPDB) / PDB               |   |   Loci Project                     |
  | - Sequences: 192,579               |   | - Sequences: 27,657                |
  | - Residues: 56,175,447 aa          |   | - Bases: 40,064,577 bp             |
  | - Size: ~265.4 MB compressed       |   | - Size: ~18.4 MB compressed        |
  | - Release: November 15, 2026       |   | - Release: November 19, 2026       |
  | - Format: BLASTDB v5 Index (.pdb)  |   | - Format: BLASTDB v5 Index (.nhr)  |
  +------------------------------------+   +------------------------------------+
```

### 1. Protein Database: `pdbaa`
- **Origin**: The **Worldwide Protein Data Bank (wwPDB)**, encompassing experimentally determined macromolecular structures solved via X-ray crystallography, cryo-electron microscopy (Cryo-EM), and NMR spectroscopy.
- **Content**: Non-redundant amino acid chains extracted from all 3D atomic coordinate records deposited in the Protein Data Bank.
- **Relevance**: Ideal for structure-to-sequence homology, catalytic active site conservation, and protein structural biology searches without requiring the 780 GB `nr` database.
- **Physical Volume Files**:
  - `pdbaa.pdb` (Sequence header index)
  - `pdbaa.phr` (Protein header information)
  - `pdbaa.pin` (Database index table)
  - `pdbaa.pog` (Offset geometry data)
  - `pdbaa.pos` (Protein sequence offset)
  - `pdbaa.pot` (Taxonomic mapping metadata)
  - `pdbaa.psq` (Binary packed amino acid sequences)
  - `pdbaa.ptf` / `pdbaa.pto` (BLASTDB v5 fast indexing)

### 2. Nucleotide Database: `16S_ribosomal_RNA`
- **Origin**: The **NCBI Targeted Loci Project** and RefSeq microbial collection.
- **Content**: Curated 16S ribosomal RNA sequences exclusively from Bacteria and Archaea type strains and validated reference cultures.
- **Relevance**: The universal phylogenetic marker for bacterial genus and species differentiation. Used worldwide for clinical pathogen detection, environmental microbiome profiling, and taxonomy.
- **Physical Volume Files**:
  - `16S_ribosomal_RNA.ndb` (Sequence header index)
  - `16S_ribosomal_RNA.nhr` (Nucleotide headers)
  - `16S_ribosomal_RNA.nin` (Database index)
  - `16S_ribosomal_RNA.nog` (Offset index)
  - `16S_ribosomal_RNA.nos` (Offset sequence data)
  - `16S_ribosomal_RNA.not` (Taxonomy lookup table)
  - `16S_ribosomal_RNA.nsq` (Binary packed nucleotide sequence stream)
  - `16S_ribosomal_RNA.ntf` / `16S_ribosomal_RNA.nto` (BLASTDB v5 fast indexing)

---

## 4. How We Are Doing It (Detailed Architectural Pipeline)

The system is engineered as a modular pipeline following strict separation of concerns across presentation, routing, validation, execution, and parsing:

```
[User Browser]
       |
       | (1) HTTP POST: Sequence + Parameters (or FASTA file)
       v
[Flask Web Application: app/app.py]
       |
       | (2) Input Sanitization & IUPAC Alphabet Validation
       v
[Validation & Security Guard: blast_service.py]
       |
       |-- Check 1: Sequence non-empty & length <= 100,000 chars
       |-- Check 2: Alphabet compliance (IUPAC nt or IUPAC aa)
       |-- Check 3: Program vs Database compatibility (e.g. blastn against nucleotide only)
       |
       | (3) Safe Subprocess Dispatch (shell=False, argument list, 45s timeout)
       v
[NCBI BLAST+ 2.16.0 Native Executable]
       |
       |-- Direct Binary Index Query against blastdb/pdbaa or blastdb/16S_ribosomal_RNA
       |
       | (4) Parallel Generation of Output Artifacts
       v
[jobs/<job_id>/results.xml] & [jobs/<job_id>/results.tsv]
       |
       | (5) BioPython NCBIXML Stream Parser
       v
[Query Coverage (Set-Union) & Metric Extractor]
       |
       | (6) Rendered Jinja2 HTML or Download Stream
       v
[Responsive Results View / TSV / XML / JSON Download]
```

### Step 4.1: Input Validation and Alphabet Discrimination
Raw input sequences are sanitized by removing non-alphabetic whitespace and converting characters to uppercase. An automated character-frequency detector identifies whether the query is nucleotide ($>90\%$ `A, C, G, T, U, N`) or protein. Any illegal characters or shell escape attempts are intercepted and rejected prior to process execution.

### Step 4.2: Isolated Job Sandboxing
Each query generates a unique UUID4 token (e.g. `1230dac1-eaab-45f7-96bd-cc24cf7de080`). A dedicated directory under `jobs/<job_id>` is created to contain:
- `query.fasta`: Cleaned, validated query sequence.
- `results.xml`: NCBI XML format (`-outfmt 5`) used for BioPython parsing.
- `results.tsv`: Tabular format (`-outfmt 6`) containing custom tabular columns for instant spreadsheet export.
- `results.json`: JSON structure representing all hits and HSP properties.

### Step 4.3: Secure Subprocess Execution
To ensure complete immunity against command injection vulnerabilities, the application prohibits `shell=True`. Commands are strictly dispatched as parameter lists:
```python
cmd = [
    program,
    "-db", db_path,
    "-query", query_file,
    "-evalue", str(evalue),
    "-max_target_seqs", str(max_target_seqs),
    "-outfmt", "5",
    "-out", xml_out_file
]
subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, env=env)
```

### Step 4.4: BioPython Parsing and Exact Set-Union Coverage Calculation
Parsing raw BLAST output through string regex is brittle. We utilize `Bio.Blast.NCBIXML.parse()` to traverse alignments. 

Standard BLAST tabular outputs often report coverage per individual High-Scoring Pair (HSP). For queries that match across multiple fragmented exons or domains, summing individual HSP lengths introduces inaccuracies due to overlapping coordinates. Our service implements an exact coordinate set-union:
```python
covered_positions = set()
for hsp in alignment.hsps:
    covered_positions.update(range(hsp.query_start, hsp.query_end + 1))
coverage_pct = round((len(covered_positions) / query_len) * 100, 2)
```
This guarantees mathematical accuracy for all reported coverage percentages.

### Step 4.5: NCBI-Standard Visual Alignment Formatting
Each HSP sequence is split into 60-character blocks with dynamic coordinate tracking for both query and subject sequences, reproducing the familiar NCBI BLAST pairwise alignment interface directly inside the web browser.
