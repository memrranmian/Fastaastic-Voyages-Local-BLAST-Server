# 3 to 5 Minute Demo Video & Live Presentation Script

**Project:** Local NCBI BLAST+ Web Server  
**Course:** Bioinformatics (MS Data Science)  
**Instructor:** Dr. Shahid Manzoor  

---

## Slide / Screen 1: Introduction (0:00 - 0:45)
- **Action**: Show terminal and project root.
- **Talking Points**:
  - *"Hello everyone. Today I am presenting our Local NCBI BLAST+ Web Server built for fast, secure, and private sequence alignment."*
  - *"We installed NCBI BLAST+ version 2.16.0 inside an isolated Ubuntu WSL2 environment and configured two local databases: `pdbaa` for protein structures and `16S_ribosomal_RNA` for bacterial phylogenetic identification."*
  - *"We developed a Flask-based web interface integrated with BioPython to parse alignments, calculate query coverage, and provide instant downloads."*

---

## Slide / Screen 2: System Architecture & Security (0:45 - 1:30)
- **Action**: Briefly show `README.md` or the generated PDF report architecture diagram.
- **Talking Points**:
  - *"For security and robustness, user inputs are strictly validated against IUPAC alphabets and checked for length limits."*
  - *"Crucially, all BLAST commands are invoked using list-based argument arrays with `shell=False` to eliminate command injection vulnerabilities entirely."*
  - *"Searches are given isolated temporary workspaces per job ID and execution timeouts to protect system stability."*

---

## Slide / Screen 3: Live Query 1 - Protein Alignment (1:30 - 2:30)
- **Action**: Open `http://localhost:5000` in the browser. Click **Hemoglobin (Protein)** sample link.
- **Talking Points**:
  - *"Here is the web interface. I'll load our first test sequence: human Hemoglobin Alpha."*
  - *"The system automatically sets the program to `blastp` and database to `pdbaa`."*
  - *Click 'Execute BLAST Search' -> View results page.*
  - *"Within approximately 3.7 seconds, the search returns full alignments. Notice our summary table with query coverage at 100%, identity at 100%, an E-value of 7e-100, and a bit score of 284."*
  - *"Scrolling down, we see the 60-character block alignments showing identical amino acid identities."*
  - *"We can also export these results in TSV, XML, JSON, or FASTA with a single click."*

---

## Slide / Screen 4: Live Query 2 - Bacterial 16S DNA & Background Jobs (2:30 - 3:45)
- **Action**: Return to home page. Click **16S rRNA (DNA)**. Toggle **Run as Asynchronous Background Job**.
- **Talking Points**:
  - *"Now let's test a nucleotide sequence: an E. coli 16S rRNA fragment."*
  - *"This switches the program to `blastn` and database to `16S_ribosomal_RNA`."*
  - *"By enabling background execution, heavy searches return an asynchronous Job ID immediately and poll the server until finished."*
  - *Click Submit -> observe `job_status.html` transition -> redirected to results.*
  - *"The search completed in 1.2 seconds, matching Enterobacteriaceae 16S rRNA with 99.2% identity and an E-value of 3.39e-126."*

---

## Slide / Screen 5: Test Automation & Conclusion (3:45 - 4:45)
- **Action**: Switch to terminal and run `pytest -v tests/test_blast_app.py`.
- **Talking Points**:
  - *"To ensure 100% precision and reliability, we implemented an automated Pytest suite testing validation errors, database mismatches, and alignment accuracy."*
  - *"All 8 tests pass with zero errors."*
  - *"The project includes the complete source code, README, requirements file, demo script, and an exhaustive 5-page PDF report."*
  - *"Thank you!"*
