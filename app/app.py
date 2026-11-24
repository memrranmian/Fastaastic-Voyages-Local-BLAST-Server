"""
Flask Application for Local NCBI BLAST Web Server
Full support for input validation, background/synchronous jobs, parameter selection,
interactive results tables, visual alignments, and multi-format downloads.
"""

import os
import json
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, abort
from blast_service import (
    run_blast_search, validate_input, DATABASES, PROGRAM_COMPATIBILITY,
    JOBS_DIR, MAX_UPLOAD_SIZE
)

app = Flask(__name__)
app.secret_key = "bioinformatics_local_blast_server_key"
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE

# In-memory registry for jobs
JOB_STORE = {}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", databases=DATABASES)

@app.route("/submit", methods=["POST"])
def submit_blast():
    # Retrieve form fields
    program = request.form.get("program", "blastp")
    database = request.form.get("database", "pdbaa")
    evalue = request.form.get("evalue", "10.0")
    max_target_seqs = request.form.get("max_target_seqs", "50")
    word_size = request.form.get("word_size", "").strip() or None
    matrix = request.form.get("matrix", "BLOSUM62").strip() or None
    perc_identity = request.form.get("perc_identity", "").strip() or None
    qcov_hsp_perc = request.form.get("qcov_hsp_perc", "").strip() or None
    is_async = request.form.get("async_mode") == "1"

    # Input sequence: file or pasted text
    query_text = request.form.get("sequence_text", "").strip()
    if 'fasta_file' in request.files:
        file = request.files['fasta_file']
        if file and file.filename != '':
            try:
                file_content = file.read().decode('utf-8', errors='replace')
                if file_content.strip():
                    query_text = file_content.strip()
            except Exception as e:
                flash(f"Error reading uploaded file: {str(e)}", "danger")
                return redirect(url_for('index'))

    # Validate input sequence format and length
    is_valid, sanitized_fasta, detected_type, err_msg = validate_input(query_text)
    if not is_valid:
        flash(f"Validation Error: {err_msg}", "danger")
        return redirect(url_for('index'))

    # Parse numeric options
    try:
        evalue_val = float(evalue)
    except ValueError:
        flash("Invalid E-value threshold.", "danger")
        return redirect(url_for('index'))

    try:
        max_seqs_val = int(max_target_seqs)
    except ValueError:
        flash("Invalid max target sequences number.", "danger")
        return redirect(url_for('index'))

    # Background Job Execution Option
    if is_async:
        import uuid
        job_id = str(uuid.uuid4())
        JOB_STORE[job_id] = {
            "status": "RUNNING",
            "program": program,
            "database": database,
            "results": None,
            "error": None
        }

        def worker(jid):
            jid, results, error = run_blast_search(
                program=program,
                db_name=database,
                query_fasta=sanitized_fasta,
                evalue=evalue_val,
                max_target_seqs=max_seqs_val,
                word_size=word_size,
                matrix=matrix,
                perc_identity=perc_identity,
                qcov_hsp_perc=qcov_hsp_perc
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

    # Synchronous Execution
    job_id, results, error = run_blast_search(
        program=program,
        db_name=database,
        query_fasta=sanitized_fasta,
        evalue=evalue_val,
        max_target_seqs=max_seqs_val,
        word_size=word_size,
        matrix=matrix,
        perc_identity=perc_identity,
        qcov_hsp_perc=qcov_hsp_perc
    )

    if error:
        flash(f"Execution Error: {error}", "danger")
        return redirect(url_for('index'))

    JOB_STORE[job_id] = {
        "status": "COMPLETED",
        "program": program,
        "database": database,
        "results": results,
        "error": None
    }
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
    return jsonify({
        "status": job["status"],
        "error": job["error"],
        "program": job["program"],
        "database": job["database"]
    })

@app.route("/results/<job_id>", methods=["GET"])
def view_results(job_id):
    job = JOB_STORE.get(job_id)
    if not job or not job.get("results"):
        flash("Results not found or job has expired.", "warning")
        return redirect(url_for('index'))
    return render_template("results.html", job_id=job_id, results=job["results"])

@app.route("/download/<job_id>/<file_format>", methods=["GET"])
def download_results(job_id, file_format):
    job_dir = os.path.join(JOBS_DIR, job_id)
    if not os.path.exists(job_dir):
        abort(404, description="Job files not found.")

    if file_format == "tsv":
        file_path = os.path.join(job_dir, "results.tsv")
        return send_file(file_path, as_attachment=True, download_name=f"blast_results_{job_id[:8]}.tsv")
    elif file_format == "xml":
        file_path = os.path.join(job_dir, "results.xml")
        return send_file(file_path, as_attachment=True, download_name=f"blast_results_{job_id[:8]}.xml")
    elif file_format == "json":
        job = JOB_STORE.get(job_id)
        if job and job.get("results"):
            json_path = os.path.join(job_dir, "results.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(job["results"], f, indent=2)
            return send_file(json_path, as_attachment=True, download_name=f"blast_results_{job_id[:8]}.json")
        abort(404, description="JSON results unavailable.")
    elif file_format == "fasta":
        file_path = os.path.join(job_dir, "query.fasta")
        return send_file(file_path, as_attachment=True, download_name=f"query_{job_id[:8]}.fasta")
    else:
        abort(400, description="Invalid download format.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
