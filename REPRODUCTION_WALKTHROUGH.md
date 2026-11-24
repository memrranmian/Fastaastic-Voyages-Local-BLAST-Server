# Step-by-Step Reproduction Guide: Local NCBI BLAST+ Web Server

This document is a comprehensive, deterministic walkthrough that enables any student, researcher, or evaluator to reproduce this entire project **from scratch** on a clean machine (Windows with WSL2, native Linux, or macOS).

---

## 1. System Requirements & Prerequisites

| Component | Minimum Specification | Recommended Specification |
|---|---|---|
| **OS** | Windows 10/11 (with WSL2) or Ubuntu 20.04+ | Ubuntu 22.04 / 24.04 LTS (native or WSL2) |
| **CPU** | 2 Cores | 4+ Cores (for multithreaded BLAST) |
| **RAM** | 4 GB | 8 GB+ |
| **Disk Space** | 2 GB free space | 5 GB free space (for indexed databases) |
| **Python** | Python 3.10+ | Python 3.12 or 3.14 |

---

## 2. Phase 1: Environment Initialization

### Step 1.1: Enable WSL2 and Install Ubuntu (Windows Users Only)
Open **PowerShell as Administrator** and execute:
```powershell
wsl --install -d Ubuntu
```
Restart your computer if prompted. After rebooting, open the **Ubuntu** application and configure your default Linux username and password.

### Step 1.2: Update System Repositories and Install Dependencies
Inside your Ubuntu terminal, run:
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ncbi-blast+ libwww-perl perl-doc python3 python3-pip python3-venv curl
```

### Step 1.3: Verify CLI Installations
Run the following commands to confirm that BLAST+ and Perl utilities are properly linked to system paths:
```bash
blastp -version
blastn -version
update_blastdb.pl --version
```
Expected output:
```
blastp: 2.16.0+
blastn: 2.16.0+
```

*(Note: If `update_blastdb.pl` is installed as `/usr/bin/update_blastdb`, create a symlink: `sudo ln -sf /usr/bin/update_blastdb /usr/local/bin/update_blastdb.pl`).*

---

## 3. Phase 2: Directory Setup & Database Ingestion

### Step 2.1: Establish Workspace Directory
Navigate to your desired project directory:
```bash
mkdir -p ~/biproj5 && cd ~/biproj5
mkdir -p blastdb jobs app/templates app/static tests docs/screenshots
```

### Step 2.2: Download and Decompress Official NCBI Databases
Run `update_blastdb.pl` inside the `blastdb/` directory to fetch both the protein and nucleotide databases:
```bash
cd blastdb

# Download and decompress the protein database (pdbaa ~265MB)
update_blastdb.pl --decompress pdbaa

# Download and decompress the microbial nucleotide database (16S_ribosomal_RNA ~18MB)
update_blastdb.pl --decompress 16S_ribosomal_RNA

cd ..
```

### Step 2.3: Validate Database Index Integrity
Export the database directory environment variable and verify volume statistics:
```bash
export BLASTDB=$(pwd)/blastdb

blastdbcmd -db pdbaa -info
blastdbcmd -db 16S_ribosomal_RNA -info
```
You should see:
- `pdbaa`: 192,579 sequences; 56,175,447 total residues.
- `16S_ribosomal_RNA`: 27,657 sequences; 40,064,577 total bases.

---

## 4. Phase 3: Isolated Python Virtual Environment

### Step 3.1: Create and Activate Virtual Environment
```bash
cd ~/biproj5
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3.2: Create `requirements.txt`
Create the pinned dependencies file:
```bash
cat << 'EOF' > requirements.txt
flask==3.1.3
biopython==1.88
reportlab==5.1.0
requests==2.34.2
pytest==9.2.0
jinja2==3.1.6
werkzeug==3.1.9
numpy==2.5.5
pillow==13.0.0
EOF
```

### Step 3.3: Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Phase 4: Application Code Setup

### Step 4.1: Create `app/blast_service.py`
Create the core alignment and BioPython parsing engine:
```bash
cat << 'EOF' > app/blast_service.py
import os
import re
import uuid
import subprocess
from datetime import datetime
from Bio.Blast import NCBIXML

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLASTDB_DIR = os.path.join(WORKSPACE_DIR, "blastdb")
JOBS_DIR = os.path.join(WORKSPACE_DIR, "jobs")

MAX_SEQUENCE_LENGTH = 100000
MAX_UPLOAD_SIZE = 2 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 45

DATABASES = {
    "pdbaa": {
        "name": "PDB Protein Database (pdbaa)",
        "type": "protein",
        "description": "Experimentally determined 3D structures from PDB"
    },
    "16S_ribosomal_RNA": {
        "name": "16S Ribosomal RNA (Bacteria & Archaea)",
        "type": "nucleotide",
        "description": "Target strain 16S rRNA sequences for bacterial identification"
    }
}

PROGRAM_COMPATIBILITY = {
    "blastn": {"query": "nucleotide", "db": "nucleotide"},
    "blastp": {"query": "protein", "db": "protein"},
    "blastx": {"query": "nucleotide", "db": "protein"},
    "tblastn": {"query": "protein", "db": "nucleotide"},
    "tblastx": {"query": "nucleotide", "db": "nucleotide"}
}

def detect_sequence_type(seq_text):
    clean_seq = re.sub(r'[^A-Za-z]', '', seq_text.upper())
    if not clean_seq:
        return None, 0.0
    nt_chars = sum(1 for c in clean_seq if c in 'ACGTUN')
    ratio = nt_chars / len(clean_seq)
    if ratio >= 0.90:
        return 'nucleotide', ratio
    return 'protein', ratio

def validate_input(raw_input):
    if not raw_input or not raw_input.strip():
        return False, None, None, "No sequence provided. Please paste a sequence or upload a FASTA file."
    lines = raw_input.strip().splitlines()
    header = ">query"
    seq_lines = []
    if lines[0].strip().startswith(">"):
        header = lines[0].strip()
        seq_lines = [l.strip() for l in lines[1:] if l.strip() and not l.startswith("#")]
    else:
        seq_lines = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
    seq = "".join(seq_lines).replace(" ", "").upper()
    if len(seq) == 0:
        return False, None, None, "Sequence content is empty."
    if len(seq) > MAX_SEQUENCE_LENGTH:
        return False, None, None, f"Sequence length ({len(seq)}) exceeds limit ({MAX_SEQUENCE_LENGTH})."
    invalid_chars = set(re.findall(r'[^A-Z\*\-\s]', seq))
    if invalid_chars:
        return False, None, None, f"Sequence contains invalid characters: {' '.join(sorted(invalid_chars))}"
    detected_type, _ = detect_sequence_type(seq)
    wrapped_seq = "\n".join(seq[i:i+70] for i in range(0, len(seq), 70))
    sanitized_fasta = f"{header}\n{wrapped_seq}\n"
    return True, sanitized_fasta, detected_type, None

def run_blast_search(program, db_name, query_fasta, evalue=10.0, max_target_seqs=50,
                     word_size=None, matrix="BLOSUM62", perc_identity=None, qcov_hsp_perc=None,
                     timeout=DEFAULT_TIMEOUT_SECONDS):
    if program not in PROGRAM_COMPATIBILITY:
        return None, None, f"Unsupported program '{program}'."
    if db_name not in DATABASES:
        return None, None, f"Database '{db_name}' is not configured."
    compat = PROGRAM_COMPATIBILITY[program]
    db_type = DATABASES[db_name]["type"]
    if compat["db"] != db_type:
        return None, None, f"Database mismatch: '{program}' requires a {compat['db']} database, but '{db_name}' is {db_type}."
    valid, sanitized_fasta, detected_type, err = validate_input(query_fasta)
    if not valid:
        return None, None, err
    if detected_type != compat["query"]:
        return None, None, f"Input mismatch: Query is {detected_type}, but {program} requires {compat['query']}."

    job_id = str(uuid.uuid4())
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    query_file = os.path.join(job_dir, "query.fasta")
    xml_out_file = os.path.join(job_dir, "results.xml")
    tsv_out_file = os.path.join(job_dir, "results.tsv")

    with open(query_file, "w", encoding="utf-8") as f:
        f.write(sanitized_fasta)

    db_path = os.path.join(BLASTDB_DIR, db_name)
    cmd_xml = [
        program, "-db", db_path, "-query", query_file,
        "-evalue", str(evalue), "-max_target_seqs", str(max_target_seqs),
        "-outfmt", "5", "-out", xml_out_file
    ]
    if word_size is not None and str(word_size).isdigit():
        cmd_xml.extend(["-word_size", str(word_size)])
    if program in ["blastp", "blastx", "tblastn"] and matrix:
        cmd_xml.extend(["-matrix", str(matrix)])
    if perc_identity is not None and str(perc_identity).strip():
        cmd_xml.extend(["-perc_identity", str(perc_identity)])
    if qcov_hsp_perc is not None and str(qcov_hsp_perc).strip():
        cmd_xml.extend(["-qcov_hsp_perc", str(qcov_hsp_perc)])

    env = os.environ.copy()
    env["BLASTDB"] = BLASTDB_DIR

    start_time = datetime.now()
    try:
        proc = subprocess.run(cmd_xml, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout, env=env)
        if proc.returncode != 0:
            return job_id, None, f"BLAST error: {proc.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return job_id, None, f"BLAST execution timed out after {timeout} seconds."

    elapsed_seconds = (datetime.now() - start_time).total_seconds()

    cmd_tsv = [
        program, "-db", db_path, "-query", query_file,
        "-evalue", str(evalue), "-max_target_seqs", str(max_target_seqs),
        "-outfmt", "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore qcovs stitle",
        "-out", tsv_out_file
    ]
    subprocess.run(cmd_tsv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    parsed_results = parse_blast_xml(xml_out_file, program, db_name, elapsed_seconds)
    parsed_results["job_id"] = job_id
    parsed_results["tsv_file"] = tsv_out_file
    parsed_results["xml_file"] = xml_out_file
    parsed_results["query_file"] = query_file
    return job_id, parsed_results, None

def parse_blast_xml(xml_file_path, program, db_name, elapsed_seconds):
    if not os.path.exists(xml_file_path):
        return {"hits": [], "total_hits": 0, "query_id": "N/A", "query_len": 0, "elapsed_seconds": elapsed_seconds}
    hits = []
    query_id = "N/A"
    query_len = 0
    with open(xml_file_path, "r", encoding="utf-8") as f:
        try:
            for record in NCBIXML.parse(f):
                query_id = record.query
                query_len = record.query_length
                for alignment in record.alignments:
                    best_hsp = alignment.hsps[0]
                    covered_positions = set()
                    for hsp in alignment.hsps:
                        covered_positions.update(range(hsp.query_start, hsp.query_end + 1))
                    coverage_pct = round((len(covered_positions) / query_len) * 100, 2) if query_len > 0 else 0.0
                    identity_pct = round((best_hsp.identities / best_hsp.align_length) * 100, 2) if best_hsp.align_length > 0 else 0.0
                    hit_info = {
                        "hit_id": alignment.hit_id,
                        "hit_def": alignment.hit_def,
                        "accession": alignment.accession,
                        "length": alignment.length,
                        "query_coverage": coverage_pct,
                        "percent_identity": identity_pct,
                        "evalue": f"{best_hsp.expect:.2e}" if best_hsp.expect < 1e-4 else round(best_hsp.expect, 4),
                        "bit_score": round(best_hsp.bits, 1),
                        "hsps": []
                    }
                    for i, hsp in enumerate(alignment.hsps, 1):
                        hit_info["hsps"].append({
                            "hsp_num": i,
                            "score": round(hsp.bits, 1),
                            "evalue": f"{hsp.expect:.2e}" if hsp.expect < 1e-4 else round(hsp.expect, 4),
                            "identities": hsp.identities,
                            "align_len": hsp.align_length,
                            "identity_pct": round((hsp.identities / hsp.align_length) * 100, 1),
                            "gaps": hsp.gaps,
                            "formatted_blocks": format_alignment_blocks(hsp.query, hsp.match, hsp.sbjct, hsp.query_start, hsp.sbjct_start)
                        })
                    hits.append(hit_info)
        except Exception as e:
            print(f"Error parsing XML: {e}")
    return {
        "program": program, "database": db_name, "query_id": query_id,
        "query_length": query_len, "total_hits": len(hits),
        "elapsed_seconds": round(elapsed_seconds, 3), "hits": hits
    }

def format_alignment_blocks(q_seq, m_seq, s_seq, q_start, s_start, block_size=60):
    blocks = []
    curr_q = q_start
    curr_s = s_start
    for i in range(0, len(q_seq), block_size):
        chunk_q = q_seq[i:i+block_size]
        chunk_m = m_seq[i:i+block_size]
        chunk_s = s_seq[i:i+block_size]
        end_q = curr_q + max(0, len(chunk_q.replace("-", "")) - 1)
        end_s = curr_s + max(0, len(chunk_s.replace("-", "")) - 1)
        blocks.append({
            "q_num_start": curr_q, "q_seq": chunk_q, "q_num_end": end_q,
            "match": chunk_m, "s_num_start": curr_s, "s_seq": chunk_s, "s_num_end": end_s
        })
        curr_q = end_q + 1
        curr_s = end_s + 1
    return blocks
EOF
```

### Step 4.2: Create `app/app.py`
Create the Flask web application routes:
```bash
cat << 'EOF' > app/app.py
import os
import json
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, abort
from blast_service import run_blast_search, validate_input, DATABASES, JOBS_DIR, MAX_UPLOAD_SIZE

app = Flask(__name__)
app.secret_key = "bioinformatics_local_blast_server_key"
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE
JOB_STORE = {}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", databases=DATABASES)

@app.route("/submit", methods=["POST"])
def submit_blast():
    program = request.form.get("program", "blastp")
    database = request.form.get("database", "pdbaa")
    evalue = request.form.get("evalue", "10.0")
    max_target_seqs = request.form.get("max_target_seqs", "50")
    word_size = request.form.get("word_size", "").strip() or None
    matrix = request.form.get("matrix", "BLOSUM62").strip() or None
    perc_identity = request.form.get("perc_identity", "").strip() or None
    qcov_hsp_perc = request.form.get("qcov_hsp_perc", "").strip() or None
    is_async = request.form.get("async_mode") == "1"

    query_text = request.form.get("sequence_text", "").strip()
    if 'fasta_file' in request.files:
        file = request.files['fasta_file']
        if file and file.filename != '':
            try:
                content = file.read().decode('utf-8', errors='replace').strip()
                if content:
                    query_text = content
            except Exception as e:
                flash(f"Error reading file: {str(e)}", "danger")
                return redirect(url_for('index'))

    is_valid, sanitized_fasta, detected_type, err_msg = validate_input(query_text)
    if not is_valid:
        flash(f"Validation Error: {err_msg}", "danger")
        return redirect(url_for('index'))

    try:
        evalue_val = float(evalue)
        max_seqs_val = int(max_target_seqs)
    except ValueError:
        flash("Invalid numeric parameter format.", "danger")
        return redirect(url_for('index'))

    if is_async:
        import uuid
        job_id = str(uuid.uuid4())
        JOB_STORE[job_id] = {"status": "RUNNING", "program": program, "database": database, "results": None, "error": None}
        def worker(jid):
            jid, results, error = run_blast_search(
                program=program, db_name=database, query_fasta=sanitized_fasta,
                evalue=evalue_val, max_target_seqs=max_seqs_val, word_size=word_size,
                matrix=matrix, perc_identity=perc_identity, qcov_hsp_perc=qcov_hsp_perc
            )
            if error:
                JOB_STORE[jid]["status"] = "FAILED"
                JOB_STORE[jid]["error"] = error
            else:
                JOB_STORE[jid]["status"] = "COMPLETED"
                JOB_STORE[jid]["results"] = results

        thread = threading.Thread(target=worker, args=(job_id,))
        thread.daemon = True
        thread.start()
        return redirect(url_for('job_status_view', job_id=job_id))

    job_id, results, error = run_blast_search(
        program=program, db_name=database, query_fasta=sanitized_fasta,
        evalue=evalue_val, max_target_seqs=max_seqs_val, word_size=word_size,
        matrix=matrix, perc_identity=perc_identity, qcov_hsp_perc=qcov_hsp_perc
    )
    if error:
        flash(f"Execution Error: {error}", "danger")
        return redirect(url_for('index'))

    JOB_STORE[job_id] = {"status": "COMPLETED", "program": program, "database": database, "results": results, "error": None}
    return redirect(url_for('view_results', job_id=job_id))

@app.route("/job/<job_id>", methods=["GET"])
def job_status_view(job_id):
    job = JOB_STORE.get(job_id)
    if not job:
        flash("Job ID not found.", "warning")
        return redirect(url_for('index'))
    if job["status"] == "COMPLETED":
        return redirect(url_for('view_results', job_id=job_id))
    return render_template("job_status.html", job_id=job_id, job=job)

@app.route("/api/job/<job_id>", methods=["GET"])
def api_job_status(job_id):
    job = JOB_STORE.get(job_id)
    if not job:
        return jsonify({"status": "NOT_FOUND"}), 404
    return jsonify({"status": job["status"], "error": job["error"]})

@app.route("/results/<job_id>", methods=["GET"])
def view_results(job_id):
    job = JOB_STORE.get(job_id)
    if not job or not job.get("results"):
        flash("Results not found.", "warning")
        return redirect(url_for('index'))
    return render_template("results.html", job_id=job_id, results=job["results"])

@app.route("/download/<job_id>/<file_format>", methods=["GET"])
def download_results(job_id, file_format):
    job_dir = os.path.join(JOBS_DIR, job_id)
    if not os.path.exists(job_dir):
        abort(404)
    if file_format == "tsv":
        return send_file(os.path.join(job_dir, "results.tsv"), as_attachment=True, download_name=f"blast_{job_id[:8]}.tsv")
    elif file_format == "xml":
        return send_file(os.path.join(job_dir, "results.xml"), as_attachment=True, download_name=f"blast_{job_id[:8]}.xml")
    elif file_format == "json":
        job = JOB_STORE.get(job_id)
        if job and job.get("results"):
            json_path = os.path.join(job_dir, "results.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(job["results"], f, indent=2)
            return send_file(json_path, as_attachment=True, download_name=f"blast_{job_id[:8]}.json")
        abort(404)
    elif file_format == "fasta":
        return send_file(os.path.join(job_dir, "query.fasta"), as_attachment=True, download_name=f"query_{job_id[:8]}.fasta")
    abort(400)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
EOF
```

*(Note: The corresponding templates `index.html`, `results.html`, and `job_status.html` are located in `app/templates/` as detailed in the project repository).*

---

## 6. Phase 5: Verification & Testing

### Step 6.1: Run the Automated Pytest Suite
Execute the full test suite to confirm 100% test passing:
```bash
source .venv/bin/activate
export BLASTDB=$(pwd)/blastdb
pytest -v tests/test_blast_app.py
```
Expected output:
```
tests/test_blast_app.py::test_home_page PASSED
tests/test_blast_app.py::test_validation_empty_sequence PASSED
tests/test_blast_app.py::test_validation_invalid_characters PASSED
tests/test_blast_app.py::test_program_db_mismatch PASSED
tests/test_blast_app.py::test_query_1_protein_hemoglobin PASSED
tests/test_blast_app.py::test_query_2_dna_16s_rrna PASSED
tests/test_blast_app.py::test_query_3_short_peptide PASSED
tests/test_blast_app.py::test_full_web_submit_flow PASSED

============================== 8 passed in 15.06s ==============================
```

### Step 6.2: Launch the Web Server
```bash
python app/app.py
```
Open your web browser and navigate to:
```
http://localhost:5000
```
Test with the built-in sample query links:
- **Hemoglobin (Protein)**: Executes `blastp` against `pdbaa`.
- **16S rRNA (DNA)**: Executes `blastn` against `16S_ribosomal_RNA`.
- **Tricky Short Peptide**: Executes sensitive `blastp` with PAM30.
