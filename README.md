# Local NCBI BLAST+ Web Server

A bioinformatics web application built with **Flask**, **BioPython**, and **NCBI BLAST+ 2.16.0** running on an isolated Ubuntu environment within Windows Subsystem for Linux (WSL2).

---

## 1. Overview & Features

- **Multi-Program Heuristic Searches**: Supports `blastp`, `blastn`, `blastx`, `tblastn`, and `tblastx`.
- **Pre-formatted Local Databases**:
  - `pdbaa`: Protein Data Bank amino acid sequences (192,579 structures, 56.1M residues).
  - `16S_ribosomal_RNA`: Bacteria and Archaea type strain sequences (27,657 sequences, 40.0M bases).
- **Validation & Security**:
  - Command injection prevention via argument list execution (`shell=False`).
  - Strict FASTA formatting and IUPAC character verification.
  - Length and file size upload boundaries (2MB max, 100k bp/aa max).
  - Subprocess timeouts (45 seconds) to avoid runaway queries.
- **Asynchronous Background Processing**:
  - Option to execute heavy queries as background jobs with real-time polling and status tracking.
- **Rich Results & Reporting**:
  - Metrics table including Query Coverage (exact set-union coordinate calculation), % Identity, E-values, and Bit Scores.
  - Formatted 60-character pairwise alignment blocks matching standard NCBI BLAST presentation.
  - Multi-format exports: TSV/CSV, NCBI XML, JSON, and FASTA.

---

## 2. Directory Structure

```
biproj5/
├── app/
│   ├── app.py                     # Flask web server and routing
│   ├── blast_service.py           # Core BLAST execution, validation & parsing
│   ├── templates/
│   │   ├── index.html             # Sequence input & parameter configuration
│   │   ├── results.html           # Summary table & pairwise alignments
│   │   └── job_status.html        # Asynchronous job polling view
│   └── static/
├── blastdb/                       # Pre-formatted BLAST databases (pdbaa, 16S_ribosomal_RNA)
├── docs/
│   ├── Local_BLAST_Web_Server_Project_Report.pdf  # 5-6 Page Assignment PDF Report
│   └── screenshots/               # Automated browser screenshots
├── jobs/                          # Isolated per-query workspace folders
├── tests/
│   ├── test_blast_app.py          # Pytest validation test suite
│   ├── run_benchmark.py           # Benchmark script for test queries
│   └── benchmark_results.json     # Quantitative test metrics
├── .venv/                         # Isolated Python virtual environment
├── requirements.txt               # Pinned Python package dependencies
├── DEMO_SCRIPT.md                 # 3-5 minute live/recorded demo guide
└── README.md                      # Setup and execution guide
```

---

## 3. Setup and Installation

### Prerequisites
- Windows 10/11 with WSL2 enabled.
- Ubuntu distribution installed (`wsl --install -d Ubuntu`).

### Step 1: Install NCBI BLAST+ Toolkit
Inside your Ubuntu terminal:
```bash
sudo apt-get update
sudo apt-get install -y ncbi-blast+ libwww-perl perl-doc
```
Verify installation:
```bash
blastp -version
blastn -version
```

### Step 2: Set Up Python Virtual Environment
Navigate to the project root and activate the environment:
```bash
cd /mnt/d/sem-3-studies/Bioinformatics_f26/finals/assgn/biproj5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Download Databases (If not already present)
```bash
mkdir -p blastdb && cd blastdb
update_blastdb.pl --decompress pdbaa 16S_ribosomal_RNA
cd ..
```

---

## 4. Running the Web Application

Activate the virtual environment and launch the server:
```bash
source .venv/bin/activate
export BLASTDB=/mnt/d/sem-3-studies/Bioinformatics_f26/finals/assgn/biproj5/blastdb
python app/app.py
```
Open your web browser and navigate to:
```
http://localhost:5000
```

---

## 5. Running Automated Tests & Benchmarks

To execute the test suite (all 8 validation tests):
```bash
source .venv/bin/activate
export BLASTDB=/mnt/d/sem-3-studies/Bioinformatics_f26/finals/assgn/biproj5/blastdb
pytest -v tests/test_blast_app.py
```

To run the benchmark across the three test sequences:
```bash
python tests/run_benchmark.py
```

---

## 6. Regenerating the PDF Report

The comprehensive PDF report can be regenerated at any time using ReportLab:
```bash
python docs/generate_report_pdf.py
```
The output will be saved to:
`docs/Local_BLAST_Web_Server_Project_Report.pdf`
