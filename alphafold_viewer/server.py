import os
import glob
import logging
import sys
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict

# Configure logging with timestamps
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("alphafold-viewer")

app = FastAPI()

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"→ {request.method} {request.url.path}")
    if request.query_params:
        logger.debug(f"  Query params: {dict(request.query_params)}")
    
    try:
        response = await call_next(request)
        logger.info(f"← {request.method} {request.url.path} → {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"✗ {request.method} {request.url.path} → Error: {e}")
        raise

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (css, js)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("templates/index.html")

@app.get("/mutation-analysis")
async def mutation_analysis_page():
    """Serve the mutation analysis page"""
    return FileResponse("templates/mutation_analysis.html")

@app.get("/api/files")
async def list_files(path: str):
    """
    Scans the provided directory for AlphaFold output files.
    Looking for:
    - .pdb files (structures)
    - .json files (scores, pae)
    """
    logger.info(f"[list_files] Scanning directory: {path}")
    
    if not os.path.exists(path):
        logger.error(f"[list_files] ✗ Directory not found: {path}")
        raise HTTPException(status_code=404, detail="Directory not found")
    
    if not os.path.isdir(path):
        logger.error(f"[list_files] ✗ Path is not a directory: {path}")
        raise HTTPException(status_code=400, detail="Path is not a directory")

    try:
        # Find PDB files
        pdb_pattern = os.path.join(path, "*_unrelaxed_rank_*.pdb")
        logger.debug(f"[list_files] Searching for PDB: {pdb_pattern}")
        pdb_files = glob.glob(pdb_pattern)
        pdb_files = [os.path.basename(f) for f in pdb_files]
        pdb_files.sort()
        logger.info(f"[list_files] Found {len(pdb_files)} PDB files: {pdb_files}")

        # Find PAE and Score JSON files
        pae_pattern = os.path.join(path, "*_predicted_aligned_error_v1.json")
        logger.debug(f"[list_files] Searching for PAE: {pae_pattern}")
        pae_file = glob.glob(pae_pattern)
        pae_file = os.path.basename(pae_file[0]) if pae_file else None
        logger.info(f"[list_files] PAE file: {pae_file}")

        score_pattern = os.path.join(path, "*_scores_rank_*.json")
        score_files = glob.glob(score_pattern)
        score_files = [os.path.basename(f) for f in score_files]
        score_files.sort()
        logger.info(f"[list_files] Found {len(score_files)} score files: {score_files}")

        result = {
            "pdb_files": pdb_files,
            "pae_file": pae_file,
            "score_files": score_files
        }
        logger.info(f"[list_files] ✓ Returning file list")
        return result
    except Exception as e:
        logger.exception(f"[list_files] ✗ Error scanning directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search-gene")
async def search_gene(gene_name: str):
    """
    Searches for a gene and downloads AlphaFold reference structure.
    1. Query UniProt: gene_name -> UniProt ID
    2. Query AlphaFold DB: UniProt ID -> download PDB and PAE
    3. Return paths to downloaded files
    """
    import httpx
    import tempfile
    
    logger.info(f"[search_gene] Searching for: {gene_name}")
    
    # Check if input is already a UniProt ID (pattern: 1 letter + 5 alphanumeric, e.g., P35557, Q9Y6R7)
    import re
    uniprot_id_pattern = r'^[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9]$|^[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9][A-Z][A-Z0-9]{2}[0-9]$|^[OPQ][0-9][A-Z0-9]{3}[0-9]$'
    
    if re.match(uniprot_id_pattern, gene_name.upper()):
        # Input looks like a UniProt ID - skip search, use directly
        uniprot_id = gene_name.upper()
        logger.info(f"[search_gene] Input recognized as UniProt ID: {uniprot_id}")
    else:
        # Step 1: Search UniProt for the gene name
        try:
            query = f"gene_exact:{gene_name} AND organism_id:9606 AND reviewed:true"
            uniprot_url = f"https://rest.uniprot.org/uniprotkb/search?query={query}&fields=accession&size=1"
            
            async with httpx.AsyncClient() as client:
                logger.debug(f"[search_gene] Querying UniProt: {uniprot_url}")
                response = await client.get(uniprot_url, timeout=30.0)
                
                if response.status_code != 200:
                    logger.error(f"[search_gene] UniProt API error: {response.status_code}")
                    raise HTTPException(status_code=502, detail="UniProt API error")
                
                data = response.json()
                if not data.get('results'):
                    logger.warning(f"[search_gene] Gene not found: {gene_name}")
                    raise HTTPException(status_code=404, detail=f"Gene '{gene_name}' not found in UniProt. Try using the UniProt ID directly (e.g., P35557).")
                
                uniprot_id = data['results'][0]['primaryAccession']
                logger.info(f"[search_gene] ✓ Found UniProt ID: {uniprot_id}")
                
        except httpx.RequestError as e:
            logger.error(f"[search_gene] UniProt request failed: {e}")
            raise HTTPException(status_code=502, detail="Failed to connect to UniProt")
    
    # Step 2: Get AlphaFold data
    try:
        alphafold_url = f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
        
        async with httpx.AsyncClient() as client:
            logger.debug(f"[search_gene] Querying AlphaFold: {alphafold_url}")
            response = await client.get(alphafold_url, timeout=30.0)
            
            if response.status_code != 200:
                logger.error(f"[search_gene] AlphaFold API error: {response.status_code}")
                raise HTTPException(status_code=502, detail="AlphaFold API error")
            
            af_data = response.json()
            if not af_data:
                raise HTTPException(status_code=404, detail=f"No AlphaFold structure for {uniprot_id}")
            
            # Get first entry (usually there's only one)
            entry = af_data[0] if isinstance(af_data, list) else af_data
            pdb_url = entry.get('pdbUrl')
            pae_url = entry.get('paeDocUrl')  # Use the exact URL from API response!
            gene_from_api = entry.get('gene', gene_name)
            
            logger.info(f"[search_gene] ✓ Found AlphaFold entry: {entry.get('uniprotDescription', uniprot_id)}")
            logger.info(f"[search_gene]   Gene: {gene_from_api}, PDB: {pdb_url}")
            logger.info(f"[search_gene]   PAE: {pae_url}")
            
    except httpx.RequestError as e:
        logger.error(f"[search_gene] AlphaFold request failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to AlphaFold DB")
    
    # Step 3: Download files to temp directory
    try:
        # Create temp directory for reference files
        ref_dir = os.path.join(os.getcwd(), "data", "reference", uniprot_id)
        os.makedirs(ref_dir, exist_ok=True)
        
        async with httpx.AsyncClient() as client:
            # Download PDB
            logger.debug(f"[search_gene] Downloading PDB...")
            pdb_response = await client.get(pdb_url, timeout=60.0)
            pdb_path = os.path.join(ref_dir, f"{uniprot_id}.pdb")
            with open(pdb_path, 'wb') as f:
                f.write(pdb_response.content)
            logger.info(f"[search_gene] ✓ Downloaded PDB: {pdb_path}")
            
            # Download PAE JSON (using URL from API response)
            pae_path = None
            if pae_url:
                logger.debug(f"[search_gene] Downloading PAE from: {pae_url}")
                pae_response = await client.get(pae_url, timeout=60.0)
                pae_path = os.path.join(ref_dir, f"{uniprot_id}_pae.json")
                
                if pae_response.status_code == 200:
                    with open(pae_path, 'wb') as f:
                        f.write(pae_response.content)
                    logger.info(f"[search_gene] ✓ Downloaded PAE: {pae_path}")
                else:
                    pae_path = None
                    logger.warning(f"[search_gene] PAE download failed: {pae_response.status_code}")
            else:
                logger.warning(f"[search_gene] No PAE URL in API response")
        
        return {
            "uniprot_id": uniprot_id,
            "gene_name": gene_name,
            "pdb_path": ref_dir,
            "pdb_file": f"{uniprot_id}.pdb",
            "pae_file": f"{uniprot_id}_pae.json" if pae_path else None
        }
        
    except Exception as e:
        logger.exception(f"[search_gene] Download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.get("/api/data")
async def get_file_content(path: str, file: str):
    """
    Serves the content of a specific file from the directory.
    """
    logger.info(f"[get_file_content] Requested file: {file} from {path}")
    file_path = os.path.join(path, file)
    
    # Security check: ensure the file path is within the intended directory
    if not os.path.abspath(file_path).startswith(os.path.abspath(path)):
        logger.warning(f"[get_file_content] ⚠ Security: Access denied to {file_path}")
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(file_path):
        logger.error(f"[get_file_content] ✗ File not found: {file_path}")
        raise HTTPException(status_code=404, detail="File not found")

    file_size = os.path.getsize(file_path)
    logger.info(f"[get_file_content] ✓ Serving {file} ({file_size} bytes)")
    return FileResponse(file_path)


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """
    Download generated files (like combined PDB).
    """
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    file_path = os.path.join(output_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    logger.info(f"[download] Serving {filename}")
    return FileResponse(file_path, filename=filename, media_type='chemical/x-pdb')


@app.get("/api/extract-sequence")
async def extract_sequence(path: str):
    """
    Extract amino acid sequence from all PDB files in folder.
    Validates all sequences are identical.
    """
    logger.info(f"[extract] Extracting sequences from {path}")
    
    try:
        from Bio.PDB import PDBParser
        import glob
        
        three_to_one = {
            'ALA': 'A', 'CYS': 'C', 'ASP': 'D', 'GLU': 'E', 'PHE': 'F',
            'GLY': 'G', 'HIS': 'H', 'ILE': 'I', 'LYS': 'K', 'LEU': 'L',
            'MET': 'M', 'ASN': 'N', 'PRO': 'P', 'GLN': 'Q', 'ARG': 'R',
            'SER': 'S', 'THR': 'T', 'VAL': 'V', 'TRP': 'W', 'TYR': 'Y'
        }
        
        # Find all PDB files
        pdb_files = glob.glob(os.path.join(path, "*.pdb"))
        
        if not pdb_files:
            raise HTTPException(status_code=404, detail="No PDB files found")
        
        parser = PDBParser(QUIET=True)
        sequences = []
        
        for pdb_file in pdb_files:
            structure = parser.get_structure('protein', pdb_file)
            model = structure[0]
            chain = list(model.get_chains())[0]
            
            sequence = ""
            for residue in chain:
                if residue.id[0] == ' ':  # Standard residue
                    res_name = residue.resname
                    if res_name in three_to_one:
                        sequence += three_to_one[res_name]
            
            sequences.append(sequence)
            logger.info(f"[extract] {os.path.basename(pdb_file)}: {len(sequence)} AA")
        
        # Validate all sequences are identical
        if not all(seq == sequences[0] for seq in sequences):
            raise HTTPException(status_code=400, detail="PDB files contain different sequences!")
        
        logger.info(f"[extract] ✓ All {len(sequences)} PDB files have identical sequence ({len(sequences[0])} AA)")
        
        return JSONResponse(content={
            'sequence': sequences[0],
            'length': len(sequences[0]),
            'num_files': len(sequences)
        })
        
    except Exception as e:
        logger.error(f"[extract] ✗ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/detect-mutations")
async def detect_mutations(data: dict):
    """
    Compare healthy (UniProt) sequence vs mutated sequence.
    Returns all mutations with positions.
    """
    logger.info(f"[mutations] Detecting mutations")
    
    try:
        uniprot_id = data.get('uniprot_id')
        test_sequence = data.get('test_sequence', '').upper().replace(' ', '').replace('\n', '')
        
        if not uniprot_id or not test_sequence:
            raise HTTPException(status_code=400, detail="Missing uniprot_id or test_sequence")
        
        # Fetch healthy sequence from UniProt
        logger.info(f"[mutations] Fetching sequence for {uniprot_id}")
        uniprot_url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta"
        
        import requests
        response = requests.get(uniprot_url, timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail=f"UniProt ID {uniprot_id} not found")
        
        # Parse FASTA
        lines = response.text.strip().split('\n')
        header = lines[0]
        healthy_sequence = "".join(lines[1:]).upper()
        
        logger.info(f"[mutations] Healthy length: {len(healthy_sequence)}, Test length: {len(test_sequence)}")
        
        # Compare sequences
        mutations = []
        min_len = min(len(healthy_sequence), len(test_sequence))
        
        for i in range(min_len):
            if healthy_sequence[i] != test_sequence[i]:
                mutations.append({
                    'position': i + 1,  # 1-based indexing
                    'healthy_aa': healthy_sequence[i],
                    'mutated_aa': test_sequence[i],
                    'notation': f"{healthy_sequence[i]}{i+1}{test_sequence[i]}"
                })
        
        # Check for length differences
        length_diff = len(healthy_sequence) - len(test_sequence)
        
        if length_diff > 0:
            # Deletion
            deleted = healthy_sequence[len(test_sequence):]
            mutations.append({
                'position': len(test_sequence) + 1,
                'type': 'deletion',
                'count': length_diff,
                'sequence': deleted[:20] + ('...' if len(deleted) > 20 else '')
            })
        elif length_diff < 0:
            # Insertion
            inserted = test_sequence[len(healthy_sequence):]
            mutations.append({
                'position': len(healthy_sequence) + 1,
                'type': 'insertion',
                'count': abs(length_diff),
                'sequence': inserted[:20] + ('...' if len(inserted) > 20 else '')
            })
        
        result = {
            'healthy_id': uniprot_id,
            'healthy_length': len(healthy_sequence),
            'test_length': len(test_sequence),
            'mutations': mutations,
            'num_mutations': len(mutations),
            'header': header
        }
        
        logger.info(f"[mutations] ✓ Found {len(mutations)} mutations")
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"[mutations] ✗ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/compare-structures")
async def compare_structures(test_path: str, ref_path: str):
    """
    Compare two PDB structures and return difference metrics.
    Returns: TM-score, RMSD, and per-residue deviation data.
    """
    logger.info(f"[compare] Comparing structures")
    logger.debug(f"  Test: {test_path}")
    logger.debug(f"  Ref: {ref_path}")
    
    # Import the comparison utility
    try:
        from utils.structure_compare import calculate_residue_distances, generate_difference_report
    except ImportError as e:
        logger.error(f"Failed to import structure_compare: {e}")
        raise HTTPException(status_code=500, detail=f"Structure comparison module error: {str(e)}")
    
    if not os.path.exists(test_path):
        raise HTTPException(status_code=404, detail=f"Test structure not found: {test_path}")
    
    if not os.path.exists(ref_path):
        raise HTTPException(status_code=404, detail=f"Reference structure not found: {ref_path}")
    
    try:
        # Run comparison
        result = calculate_residue_distances(ref_path, test_path)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Generate text report
        report_text = generate_difference_report(result)
        result["report"] = report_text
        
        # Generate combined PDB with both structures
        try:
            from utils.pdb_combiner import create_superposed_pdb
            
            # Create output path
            output_dir = os.path.join(os.path.dirname(__file__), 'output')
            os.makedirs(output_dir, exist_ok=True)
            output_pdb = os.path.join(output_dir, 'superposed_comparison.pdb')
            
            pdb_report = create_superposed_pdb(
                ref_path, 
                test_path, 
                output_pdb,
                result['residue_deviations']
            )
            
            result['combined_pdb'] = {
                'path': output_pdb,
                'download_url': f'/api/download/superposed_comparison.pdb',
                'mutations': pdb_report['mutations'],
                'num_mutations': pdb_report['num_mutations']
            }
            
            logger.info(f"[compare] ✓ Generated combined PDB with {pdb_report['num_mutations']} mutations")
            
        except Exception as pdb_error:
            logger.warn(f"[compare] Could not generate combined PDB: {pdb_error}")
            result['combined_pdb'] = {'error': str(pdb_error)}
        
        logger.info(f"[compare] ✓ Comparison complete")
        logger.info(f"  TM-score: {result.get('tm_score', 'N/A'):.3f}")
        logger.info(f"  RMSD: {result.get('global_rmsd', 'N/A'):.3f} Å")
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"[compare] ✗ Comparison failed: {e}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


# ========================================
# Mutation Analysis Pipeline
# ========================================
from pydantic import BaseModel
from typing import Optional

class MutationAnalysisRequest(BaseModel):
    uniprot_id: str
    mutant_pdb_path: str

class MutationAnalysisResponse(BaseModel):
    success: bool
    status: Optional[str] = None
    mutation_type: Optional[str] = None
    mutations: Optional[list] = None
    scan_results: Optional[dict] = None
    pipeline_decision: Optional[str] = None
    analysis: Optional[dict] = None
    verdict: Optional[str] = None
    verdict_class: Optional[str] = None
    verdict_reason: Optional[str] = None
    error: Optional[str] = None

@app.post("/api/analyze-mutation", response_model=MutationAnalysisResponse)
async def analyze_mutation(request: MutationAnalysisRequest):
    """
    Analyze mutations between a wild-type (from UniProt) and mutant PDB.
    Routes analysis to appropriate tools based on mutation type.
    """
    logger.info(f"[mutation] Starting analysis: UniProt={request.uniprot_id}, Mutant={request.mutant_pdb_path}")
    
    try:
        from utils.analysis_router import route_analysis as run_analysis
        
        # Find wild-type PDB - check reference folder first
        wt_pdb_path = None
        ref_dir = os.path.join("data", "reference", request.uniprot_id)
        if os.path.exists(ref_dir):
            pdb_files = glob.glob(os.path.join(ref_dir, "*.pdb"))
            if pdb_files:
                wt_pdb_path = pdb_files[0]
                logger.info(f"[mutation] Found local WT PDB: {wt_pdb_path}")
        
        # If not found locally, try to download from AlphaFold
        if not wt_pdb_path:
            import requests
            alphafold_url = f"https://alphafold.ebi.ac.uk/files/AF-{request.uniprot_id}-F1-model_v4.pdb"
            logger.info(f"[mutation] Downloading WT from AlphaFold: {alphafold_url}")
            
            response = requests.get(alphafold_url, timeout=30)
            if response.status_code == 200:
                os.makedirs(ref_dir, exist_ok=True)
                wt_pdb_path = os.path.join(ref_dir, f"{request.uniprot_id}.pdb")
                with open(wt_pdb_path, 'w') as f:
                    f.write(response.text)
                logger.info(f"[mutation] Downloaded WT PDB to: {wt_pdb_path}")
            else:
                raise HTTPException(status_code=404, detail=f"Could not find PDB for UniProt ID: {request.uniprot_id}")
        
        # Verify mutant PDB exists
        if not os.path.exists(request.mutant_pdb_path):
            raise HTTPException(status_code=404, detail=f"Mutant PDB not found: {request.mutant_pdb_path}")
        
        # Run the analysis
        logger.info(f"[mutation] Running analysis: WT={wt_pdb_path}, MUT={request.mutant_pdb_path}")
        result = run_analysis(wt_pdb_path, request.mutant_pdb_path, request.uniprot_id)
        
        logger.info(f"[mutation] Analysis complete: {result.get('mutation_type', 'Unknown')} - {result.get('verdict', 'Unknown')}")
        
        # Derive verdict class for UI color-coding
        verdict = result.get("verdict", "UNKNOWN")
        verdict_class_map = {
            "PATHOGENIC": "danger",
            "LIKELY_PATHOGENIC": "warning",
            "BENIGN": "success",
            "UNCERTAIN": "secondary",
            "LOSS_OF_FUNCTION": "danger",
            "NO_MUTATION": "info"
        }
        
        return MutationAnalysisResponse(
            success=True,
            status=result.get("status"),
            mutation_type=result.get("mutation_type"),
            mutations=result.get("mutations"),
            scan_results=result.get("scan_results"),
            pipeline_decision=result.get("pipeline_decision"),
            analysis=result.get("results"),
            verdict=result.get("verdict"),
            verdict_class=result.get("verdict_class"),
            verdict_reason=result.get("verdict_reason")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[mutation] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return MutationAnalysisResponse(
            success=False,
            error=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    logger.info("="*60)
    logger.info("  AlphaFold Viewer Server")
    logger.info("="*60)
    logger.info(f"  Starting at: http://localhost:8000")
    logger.info(f"  Working directory: {os.getcwd()}")
    logger.info("="*60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
