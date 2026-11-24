"""
BLAST Web Application - Core Processing Module
Robust, secure local BLAST execution and BioPython XML parsing.
"""

import os
import re
import uuid
import shutil
import subprocess
from datetime import datetime
from Bio.Blast import NCBIXML

# Configuration
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BLASTDB_DIR = os.path.join(WORKSPACE_DIR, "blastdb")
JOBS_DIR = os.path.join(WORKSPACE_DIR, "jobs")

# Security limits
MAX_SEQUENCE_LENGTH = 100000  # 100k bp/aa
MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2MB
DEFAULT_TIMEOUT_SECONDS = 45

# Allowed database definitions
DATABASES = {
    "pdbaa": {
        "name": "PDB Protein Database (pdbaa)",
        "type": "protein",
        "description": "Experimentally determined 3D structures from PDB translated to amino acid sequences"
    },
    "16S_ribosomal_RNA": {
        "name": "16S Ribosomal RNA (Bacteria & Archaea)",
        "type": "nucleotide",
        "description": "Target strain 16S rRNA sequences for microbial phylogenetic identification"
    }
}

# Compatibility mapping between BLAST programs, query types, and target database types
PROGRAM_COMPATIBILITY = {
    "blastn": {"query": "nucleotide", "db": "nucleotide"},
    "blastp": {"query": "protein", "db": "protein"},
    "blastx": {"query": "nucleotide", "db": "protein"},
    "tblastn": {"query": "protein", "db": "nucleotide"},
    "tblastx": {"query": "nucleotide", "db": "nucleotide"}
}

def detect_sequence_type(seq_text):
    """
    Detects if raw sequence is nucleotide or protein based on character frequencies.
    Returns: ('nucleotide' or 'protein', confidence_ratio)
    """
    clean_seq = re.sub(r'[^A-Za-z]', '', seq_text.upper())
    if not clean_seq:
        return None, 0.0
    
    nt_chars = sum(1 for c in clean_seq if c in 'ACGTUN')
    ratio = nt_chars / len(clean_seq)
    
    # If 90%+ is A, C, G, T, U, N, treat as nucleotide
    if ratio >= 0.90:
        return 'nucleotide', ratio
    return 'protein', ratio

def validate_input(raw_input):
    """
    Validates FASTA or plain sequence input.
    Returns: (is_valid, sanitized_fasta_string, detected_type, error_message)
    """
    if not raw_input or not raw_input.strip():
        return False, None, None, "No sequence provided. Please paste a sequence or upload a FASTA file."
    
    lines = raw_input.strip().splitlines()
    header = ">query"
    seq_lines = []
    
    first_line = lines[0].strip()
    if first_line.startswith(">"):
        header = first_line
        seq_lines = [l.strip() for l in lines[1:] if l.strip() and not l.startswith("#")]
    else:
        seq_lines = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
        
    seq = "".join(seq_lines).replace(" ", "").upper()
    
    if len(seq) == 0:
        return False, None, None, "Sequence content is empty."
        
    if len(seq) > MAX_SEQUENCE_LENGTH:
        return False, None, None, f"Sequence length ({len(seq)} chars) exceeds maximum allowed ({MAX_SEQUENCE_LENGTH} chars)."
        
    # Check for invalid characters (standard IUPAC amino acids + nucleotides)
    invalid_chars = set(re.findall(r'[^A-Z\*\-\s]', seq))
    if invalid_chars:
        return False, None, None, f"Sequence contains invalid characters: {' '.join(sorted(invalid_chars))}"
        
    detected_type, _ = detect_sequence_type(seq)
    
    # Format into neat 70-char wrapped FASTA
    wrapped_seq = "\n".join(seq[i:i+70] for i in range(0, len(seq), 70))
    sanitized_fasta = f"{header}\n{wrapped_seq}\n"
    
    return True, sanitized_fasta, detected_type, None

def run_blast_search(program, db_name, query_fasta, evalue=10.0, max_target_seqs=50,
                     word_size=None, matrix="BLOSUM62", perc_identity=None, qcov_hsp_perc=None,
                     gapopen=None, gapextend=None, timeout=DEFAULT_TIMEOUT_SECONDS):
    """
    Executes BLAST tool securely via subprocess without shell=True.
    Returns: (job_id, result_dict, error_message)
    """
    # Program and DB checks
    if program not in PROGRAM_COMPATIBILITY:
        return None, None, f"Unsupported BLAST program '{program}'."
        
    if db_name not in DATABASES:
        return None, None, f"Database '{db_name}' is not configured or installed."
        
    compat = PROGRAM_COMPATIBILITY[program]
    db_type = DATABASES[db_name]["type"]
    
    if compat["db"] != db_type:
        return None, None, f"Database mismatch: '{program}' requires a {compat['db']} database, but '{db_name}' is a {db_type} database."
        
    # Validate query sequence
    valid, sanitized_fasta, detected_type, err = validate_input(query_fasta)
    if not valid:
        return None, None, err
        
    # Verify query compatibility
    if detected_type != compat["query"]:
        return None, None, f"Input mismatch: Query appears to be {detected_type}, but {program} requires a {compat['query']} query."
        
    # Create isolated job directory
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(JOBS_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    query_file = os.path.join(job_dir, "query.fasta")
    xml_out_file = os.path.join(job_dir, "results.xml")
    tsv_out_file = os.path.join(job_dir, "results.tsv")
    
    with open(query_file, "w", encoding="utf-8") as f:
        f.write(sanitized_fasta)
        
    # Build BLAST command list (Safe, strictly argument-list without shell=True)
    db_path = os.path.join(BLASTDB_DIR, db_name)
    
    cmd_xml = [
        program,
        "-db", db_path,
        "-query", query_file,
        "-evalue", str(evalue),
        "-max_target_seqs", str(max_target_seqs),
        "-outfmt", "5",  # XML format for BioPython parsing
        "-out", xml_out_file
    ]
    
    # Custom optional arguments
    if word_size is not None and str(word_size).isdigit():
        cmd_xml.extend(["-word_size", str(word_size)])
    if program in ["blastp", "blastx", "tblastn"] and matrix:
        cmd_xml.extend(["-matrix", str(matrix)])
    if perc_identity is not None and str(perc_identity).strip():
        cmd_xml.extend(["-perc_identity", str(perc_identity)])
    if qcov_hsp_perc is not None and str(qcov_hsp_perc).strip():
        cmd_xml.extend(["-qcov_hsp_perc", str(qcov_hsp_perc)])
    if gapopen is not None and str(gapopen).strip():
        cmd_xml.extend(["-gapopen", str(gapopen)])
    if gapextend is not None and str(gapextend).strip():
        cmd_xml.extend(["-gapextend", str(gapextend)])
        
    # Set BLASTDB env
    env = os.environ.copy()
    env["BLASTDB"] = BLASTDB_DIR
    
    start_time = datetime.now()
    try:
        proc = subprocess.run(
            cmd_xml,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=env
        )
        if proc.returncode != 0:
            return job_id, None, f"BLAST error: {proc.stderr.strip() or proc.stdout.strip()}"
    except subprocess.TimeoutExpired:
        return job_id, None, f"BLAST execution timed out after {timeout} seconds."
    except Exception as e:
        return job_id, None, f"Failed to execute BLAST: {str(e)}"
        
    elapsed_seconds = (datetime.now() - start_time).total_seconds()
    
    # Also generate TSV outfmt 6 for easy tabular download
    cmd_tsv = [
        program,
        "-db", db_path,
        "-query", query_file,
        "-evalue", str(evalue),
        "-max_target_seqs", str(max_target_seqs),
        "-outfmt", "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore qcovs stitle",
        "-out", tsv_out_file
    ]
    if word_size is not None and str(word_size).isdigit():
        cmd_tsv.extend(["-word_size", str(word_size)])
    if program in ["blastp", "blastx", "tblastn"] and matrix:
        cmd_tsv.extend(["-matrix", str(matrix)])
    if perc_identity is not None and str(perc_identity).strip():
        cmd_tsv.extend(["-perc_identity", str(perc_identity)])
    if qcov_hsp_perc is not None and str(qcov_hsp_perc).strip():
        cmd_tsv.extend(["-qcov_hsp_perc", str(qcov_hsp_perc)])
    if gapopen is not None and str(gapopen).strip():
        cmd_tsv.extend(["-gapopen", str(gapopen)])
    if gapextend is not None and str(gapextend).strip():
        cmd_tsv.extend(["-gapextend", str(gapextend)])
        
    subprocess.run(cmd_tsv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    # Parse XML results with BioPython
    parsed_results = parse_blast_xml(xml_out_file, program, db_name, elapsed_seconds)
    parsed_results["job_id"] = job_id
    parsed_results["tsv_file"] = tsv_out_file
    parsed_results["xml_file"] = xml_out_file
    parsed_results["query_file"] = query_file
    
    return job_id, parsed_results, None

def parse_blast_xml(xml_file_path, program, db_name, elapsed_seconds):
    """
    Parses BLAST XML output using Bio.Blast.NCBIXML.
    Extracts summary hit table and detailed visual alignments.
    """
    if not os.path.exists(xml_file_path):
        return {"hits": [], "total_hits": 0, "query_id": "N/A", "query_len": 0, "elapsed": elapsed_seconds}
        
    hits = []
    query_id = "N/A"
    query_len = 0
    
    with open(xml_file_path, "r", encoding="utf-8") as f:
        try:
            blast_records = NCBIXML.parse(f)
            for record in blast_records:
                query_id = record.query
                query_len = record.query_length
                for alignment in record.alignments:
                    # Collect all HSPs for coverage and metrics
                    best_hsp = alignment.hsps[0]
                    
                    # Calculate query coverage across HSPs (set union of query coordinates)
                    covered_positions = set()
                    for hsp in alignment.hsps:
                        covered_positions.update(range(hsp.query_start, hsp.query_end + 1))
                    coverage_pct = round((len(covered_positions) / query_len) * 100, 2) if query_len > 0 else 0.0
                    
                    # Compute percent identity for the primary HSP
                    identity_pct = round((best_hsp.identities / best_hsp.align_length) * 100, 2) if best_hsp.align_length > 0 else 0.0
                    
                    # Hit details
                    hit_info = {
                        "hit_id": alignment.hit_id,
                        "hit_def": alignment.hit_def,
                        "accession": alignment.accession,
                        "length": alignment.length,
                        "query_coverage": coverage_pct,
                        "percent_identity": identity_pct,
                        "evalue": f"{best_hsp.expect:.2e}" if best_hsp.expect < 1e-4 else round(best_hsp.expect, 4),
                        "bit_score": round(best_hsp.bits, 1),
                        "raw_score": best_hsp.score,
                        "hsps": []
                    }
                    
                    # Formatted HSP alignment views
                    for i, hsp in enumerate(alignment.hsps, 1):
                        hsp_data = {
                            "hsp_num": i,
                            "score": round(hsp.bits, 1),
                            "evalue": f"{hsp.expect:.2e}" if hsp.expect < 1e-4 else round(hsp.expect, 4),
                            "identities": hsp.identities,
                            "positives": hsp.positives,
                            "gaps": hsp.gaps,
                            "align_len": hsp.align_length,
                            "identity_pct": round((hsp.identities / hsp.align_length) * 100, 1),
                            "query_start": hsp.query_start,
                            "query_end": hsp.query_end,
                            "sbjct_start": hsp.sbjct_start,
                            "sbjct_end": hsp.sbjct_end,
                            "query_seq": hsp.query,
                            "match_seq": hsp.match,
                            "sbjct_seq": hsp.sbjct,
                            "formatted_blocks": format_alignment_blocks(
                                hsp.query, hsp.match, hsp.sbjct,
                                hsp.query_start, hsp.sbjct_start,
                                block_size=60
                            )
                        }
                        hit_info["hsps"].append(hsp_data)
                        
                    hits.append(hit_info)
        except Exception as e:
            print(f"Error parsing XML: {e}")
            
    return {
        "program": program,
        "database": db_name,
        "query_id": query_id,
        "query_length": query_len,
        "total_hits": len(hits),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "hits": hits
    }

def format_alignment_blocks(q_seq, m_seq, s_seq, q_start, s_start, block_size=60):
    """
    Chunks an alignment into standard NCBI BLAST readable 60-character blocks with numbering.
    """
    blocks = []
    curr_q = q_start
    curr_s = s_start
    
    for i in range(0, len(q_seq), block_size):
        chunk_q = q_seq[i:i+block_size]
        chunk_m = m_seq[i:i+block_size]
        chunk_s = s_seq[i:i+block_size]
        
        q_advance = len(chunk_q.replace("-", ""))
        s_advance = len(chunk_s.replace("-", ""))
        
        end_q = curr_q + max(0, q_advance - 1)
        end_s = curr_s + max(0, s_advance - 1)
        
        blocks.append({
            "q_num_start": curr_q,
            "q_seq": chunk_q,
            "q_num_end": end_q,
            "match": chunk_m,
            "s_num_start": curr_s,
            "s_seq": chunk_s,
            "s_num_end": end_s
        })
        
        curr_q = end_q + 1
        curr_s = end_s + 1
        
    return blocks
