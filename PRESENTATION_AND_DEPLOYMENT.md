# Project Presentation, Demonstration & Cross-System Deployment Guide

This document provides a complete guide on **how to present this project** during an evaluation or defense, along with exact operational procedures to **deploy and execute the project on any external computer or laptop**.

---

## Part 1: How to Present This Project (Oral Defense & Live Demo)

When presenting to your instructor, lab evaluators, or an academic panel, structure your presentation into four distinct segments:

```
+-----------------------------------------------------------------------------------+
|                            Presentation Flow (5 Minutes)                          |
+-----------------------------------------------------------------------------------+
| 1. Motivation & Problem (45s)    -> Why local BLAST instead of NCBI website?      |
| 2. Architecture & Security (1m)  -> Decoupled 3-tier model, shell=False immunity  |
| 3. Live System Demonstration (2m)-> Protein, Bacterial DNA, & Async Background   |
| 4. Test Verification & Q&A (1m)  -> 100% CI automated pytest suite               |
+-----------------------------------------------------------------------------------+
```

### Segment 1: Motivation & Academic Context (0:00 - 0:45)
- **Opening Statement**: *"Good morning. Today I am demonstrating our Local NCBI BLAST+ Web Server, built to provide secure, offline, high-throughput sequence alignment for research laboratory settings."*
- **Key Concepts to Highlight**:
  - Explain why public web BLAST is insufficient for enterprise research: sequence confidentiality, strict NCBI queue throttling, and the necessity of fixed database snapshots for reproducible science.
  - Mention that this server runs native **NCBI BLAST+ 2.16.0** with both protein (`pdbaa`) and microbial nucleotide (`16S_ribosomal_RNA`) indices.

### Segment 2: System Architecture & Security Defense (0:45 - 1:45)
- **Point to the Architecture Diagram** (from the generated PDF report or slides):
  - Highlight the decoupled architecture: Frontend (HTML5/Bootstrap 5), Middle-tier application & security engine (Flask 3.1 & BioPython 1.88), and native C++ heuristic engine (NCBI BLAST+).
- **Emphasize Security Compliance (Crucial for High Marks)**:
  - Explain that command injection is structurally prevented by calling BLAST as an argument array (`subprocess.run(["blastp", "-db", ...], shell=False)`).
  - Highlight strict input validation: rejection of non-IUPAC characters, sequence length boundaries ($100,000$ characters max), upload size caps ($2$ MB), and a $45$-second execution watchdog timer.

### Segment 3: Live Application Demonstration (1:45 - 3:45)
Open the browser at `http://localhost:5000` and walk through the following sequence:

1. **Demonstration 1: Protein Search (`blastp` vs `pdbaa`)**
   - Click the quick-load link: **Hemoglobin (Protein)**.
   - Show how the program dropdown automatically updates to `blastp` and database selects `pdbaa`.
   - Click **Execute BLAST Search**.
   - Show the results page:
     - Explain the **100% Query Coverage** (calculated via exact set-union coordinates across HSPs).
     - Point out the **100% Sequence Identity**, **$E$-value of $7.0 \times 10^{-100}$**, and **Bit Score of 284**.
     - Scroll to the pairwise alignment view and explain the 60-character formatted alignment blocks.
     - Click **Export TSV/CSV** to show immediate spreadsheet compatibility.

2. **Demonstration 2: Microbial Identification (`blastn` vs `16S_ribosomal_RNA`)**
   - Return to the home page and click **16S rRNA (DNA)**.
   - Notice the automatic switch to `blastn` and `16S_ribosomal_RNA`.
   - Check the box: **Run as Asynchronous Background Job**.
   - Click **Execute BLAST Search**.
   - Show the dynamic job polling status screen (`/job/<uuid>`) as it waits for completion.
   - Explain the result: Top hits identify *Enterobacter quasihormaechei* and *Salmonella enterica* with an $E$-value of $3.39 \times 10^{-126}$ and bit score of $449$.

3. **Demonstration 3: Heuristic Tuning with a Tricky Oligopeptide**
   - Load the **Tricky Short Peptide** query.
   - Explain to the evaluators why standard BLOSUM62 fails on short sequences (due to statistical significance thresholds).
   - Demonstrate how switching the matrix to **PAM30** and elevating the $E$-value threshold successfully identifies crystallographic hemoglobin beta-chain motifs.

### Segment 4: Verification, Quality Assurance & Conclusion (3:45 - 4:45)
- Switch to the terminal and execute:
  ```bash
  pytest -v tests/test_blast_app.py
  ```
- Point out that all 8 automated tests pass with 100% confidence.
- Present the generated **5-page PDF Technical Report** (`docs/Local_BLAST_Web_Server_Project_Report.pdf`) featuring executive summaries, benchmark tables, and screenshots.

---

## Part 2: How to Deploy and Run on Another System

To transfer and run this project on another computer (e.g., an instructor's evaluation laptop, a presentation computer, or a Linux cloud VM), follow these steps:

### Option A: Transfer via Zip Archive (Recommended for Offline Evaluation)

#### Step 1: Package the Project (Excluding Large Database Binaries)
The project is configured so that code, documentation, and tests are lightweight (~1 MB). In your current project directory:
```bash
# Package into a zip excluding the heavy blastdb binaries and virtual environment
zip -r biproj5_submission.zip app tests docs requirements.txt README.md DEMO_SCRIPT.md PROJECT_DESCRIPTION.md REPRODUCTION_WALKTHROUGH.md PRESENTATION_AND_DEPLOYMENT.md -x "*.venv*" "*__pycache__*" "*jobs/*"
```
*(If you wish to run the project entirely offline on the target system without re-downloading databases, include the `blastdb/` folder on an external USB drive).*

#### Step 2: Unpack on Target Machine
On the target machine (Windows with WSL2 or Ubuntu Linux):
```bash
unzip biproj5_submission.zip -d biproj5
cd biproj5
```

#### Step 3: Install BLAST+ and System Dependencies
On the target Ubuntu/WSL system:
```bash
sudo apt-get update
sudo apt-get install -y ncbi-blast+ libwww-perl perl-doc python3 python3-pip python3-venv
```

#### Step 4: Set Up Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Step 5: Setup Databases on the Target System
- **If transferring offline via USB**: Copy the `blastdb` folder directly into `biproj5/blastdb`.
- **If target machine has internet access**:
  ```bash
  mkdir -p blastdb && cd blastdb
  update_blastdb.pl --decompress pdbaa 16S_ribosomal_RNA
  cd ..
  ```

#### Step 6: Launch and Test
```bash
export BLASTDB=$(pwd)/blastdb
# Run validation tests
pytest -v tests/test_blast_app.py

# Launch web server
python app/app.py
```
Open **`http://localhost:5000`** in the browser.

---

### Option B: Quick Cross-System Verification Checklist

Before starting an evaluation on an unfamiliar machine, run this 30-second pre-flight check in terminal:

```bash
# 1. Check BLAST+ binary availability
which blastp blastn makeblastdb

# 2. Check Database environment variable
echo $BLASTDB

# 3. Check Database index readability
blastdbcmd -db pdbaa -info | head -n 3
blastdbcmd -db 16S_ribosomal_RNA -info | head -n 3

# 4. Check Python imports
python -c "import flask, Bio, reportlab; print('All Python dependencies verified!')"
```

If all 4 commands return successful output, the local web server is guaranteed to run without issues.
