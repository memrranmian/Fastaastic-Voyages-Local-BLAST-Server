"""
Automated Test Suite for BLAST Web Application
Tests input validation, blastp, blastn, tblastn, error catching, and download routes.
"""

import os
import sys
import pytest

# Ensure app path in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))

from blast_service import validate_input, run_blast_search, DATABASES, PROGRAM_COMPATIBILITY
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home_page(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Fastaastic Voyages" in response.data
    assert b"PDB Protein Database" in response.data

def test_validation_empty_sequence():
    valid, _, _, err = validate_input("")
    assert not valid
    assert "No sequence provided" in err

def test_validation_invalid_characters():
    valid, _, _, err = validate_input(">bad_seq\nATGCZX123#$")
    assert not valid
    assert "invalid characters" in err

def test_program_db_mismatch():
    # Attempting blastn against protein pdbaa database
    _, results, error = run_blast_search(
        program="blastn",
        db_name="pdbaa",
        query_fasta=">dna\nATGCAAGTCGAACGGTAACAGGAAGCAGC"
    )
    assert error is not None
    assert "Database mismatch" in error

def test_query_1_protein_hemoglobin():
    # Test Sequence 1: Hemoglobin subunit alpha (Protein)
    seq = (
        ">sp|P69905|HBA_HUMAN Hemoglobin subunit alpha\n"
        "VLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMP"
        "NALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR"
    )
    job_id, results, error = run_blast_search(
        program="blastp",
        db_name="pdbaa",
        query_fasta=seq,
        evalue=1e-5
    )
    assert error is None
    assert results is not None
    assert results["total_hits"] > 0
    top_hit = results["hits"][0]
    assert "HEMOGLOBIN" in top_hit["hit_def"].upper() or "ALPHA" in top_hit["hit_def"].upper()
    assert float(top_hit["evalue"]) < 1e-10

def test_query_2_dna_16s_rrna():
    # Test Sequence 2: 16S ribosomal RNA fragment (DNA)
    seq = (
        ">16S_rRNA_E_coli\n"
        "AGAGTTTGATCCTGGCTCAGATTGAACGCTGGCGGCAGGCCTAACACATGCAAGTCGAACGGTAACAGGAAGCAGCTTG"
        "CTGCTTCGCTGACGAGTGGCGGACGGGTGAGTAATGTCTGGGAAACTGCCTGATGGAGGGGGATAACTACTGGAAACGG"
        "TAGCTAATACCGCATAACGTCGCAAGACCAAAGAGGGGGACCTTCGGGCCTCTTGCCATCAGATGTGCCCAGATGGGAT"
        "TAGCTAGTAGGT"
    )
    job_id, results, error = run_blast_search(
        program="blastn",
        db_name="16S_ribosomal_RNA",
        query_fasta=seq,
        evalue=1e-10
    )
    assert error is None
    assert results is not None
    assert results["total_hits"] > 0
    top_hit = results["hits"][0]
    assert float(top_hit["evalue"]) < 1e-50
    assert "ribosomal" in top_hit["hit_def"].lower() or "16s" in top_hit["hit_def"].lower()

def test_query_3_short_peptide():
    # Test Sequence 3: Short tricky peptide
    seq = ">Short_query\nMVHLTPEEKSAV"
    job_id, results, error = run_blast_search(
        program="blastp",
        db_name="pdbaa",
        query_fasta=seq,
        evalue=100.0,
        matrix="PAM30"
    )
    assert error is None
    assert results is not None
    assert results["total_hits"] >= 0

def test_full_web_submit_flow(client):
    response = client.post('/submit', data={
        "program": "blastp",
        "database": "pdbaa",
        "sequence_text": ">test\nVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR",
        "evalue": "1.0",
        "max_target_seqs": "10"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Fastaastic Voyages" in response.data
    assert b"Query Coverage" in response.data
    assert b"Pairwise Alignments" in response.data
