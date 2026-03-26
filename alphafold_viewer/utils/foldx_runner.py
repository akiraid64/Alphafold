"""
FoldX Runner - Wrapper for FoldX stability calculations
Supports: Stability, BuildModel, Two-State comparison
"""

import subprocess
import os
import shutil
import glob as globmod


def _find_foldx():
    """Auto-detect FoldX executable. Checks in order:
    1. FOLDX_EXE environment variable
    2. Any foldx*.exe in the project root (parent of alphafold_viewer)
    3. 'foldx' on system PATH (Linux/Mac)
    """
    # 1. Environment variable
    env_exe = os.environ.get("FOLDX_EXE")
    if env_exe and os.path.isfile(env_exe):
        return env_exe

    # 2. Auto-detect in project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    matches = globmod.glob(os.path.join(project_root, "foldx*.exe"))
    if not matches:
        matches = globmod.glob(os.path.join(project_root, "foldx"))
    if matches:
        return matches[0]

    # 3. Check PATH
    foldx_on_path = shutil.which("foldx")
    if foldx_on_path:
        return foldx_on_path

    return None


def _find_rotabase():
    """Find rotabase.txt. Checks in order:
    1. Same directory as FoldX executable
    2. Project root
    3. FOLDX_DIR environment variable
    """
    if FOLDX_EXE:
        exe_dir = os.path.dirname(FOLDX_EXE)
        candidate = os.path.join(exe_dir, "rotabase.txt")
        if os.path.isfile(candidate):
            return candidate

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidate = os.path.join(project_root, "rotabase.txt")
    if os.path.isfile(candidate):
        return candidate

    foldx_dir = os.environ.get("FOLDX_DIR")
    if foldx_dir:
        candidate = os.path.join(foldx_dir, "rotabase.txt")
        if os.path.isfile(candidate):
            return candidate

    return None


FOLDX_EXE = _find_foldx()
ROTABASE = _find_rotabase()


def _ensure_rotabase(work_dir):
    """Copy rotabase.txt to work_dir if not already there."""
    dest = os.path.join(work_dir, "rotabase.txt")
    if not os.path.isfile(dest) and ROTABASE:
        shutil.copy(ROTABASE, dest)


def run_stability(pdb_file, work_dir=None):
    """
    Run FoldX Stability command on a single PDB.

    Returns:
        float: Total energy in kcal/mol, or None if failed
    """
    if not FOLDX_EXE:
        print("FoldX not found. Set FOLDX_EXE env var or place foldx executable in project root.")
        return None
    if not os.path.exists(pdb_file):
        return None

    pdb_name = os.path.basename(pdb_file)
    work_dir = work_dir or os.path.dirname(pdb_file) or "."

    # Copy PDB to work dir if needed
    if os.path.dirname(pdb_file) != work_dir:
        shutil.copy(pdb_file, os.path.join(work_dir, pdb_name))

    _ensure_rotabase(work_dir)
    cmd = [FOLDX_EXE, "--command=Stability", f"--pdb={pdb_name}"]
    
    try:
        result = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True, timeout=300)
        
        # Parse Total energy from output
        for line in result.stdout.split('\n'):
            if 'Total' in line and '=' in line:
                parts = line.split()
                try:
                    return float(parts[-1])
                except ValueError:
                    continue
        
        return None
        
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        print(f"FoldX error: {e}")
        return None


def run_two_state_stability(wt_pdb, mut_pdb, work_dir=None):
    """
    Run FoldX Stability on both WT and Mutant, calculate DDG.
    
    This is the correct method for deletions/insertions where
    BuildModel cannot be used.
    
    Returns:
        dict: {
            "wt_energy": float,
            "mut_energy": float,
            "ddg": float,
            "interpretation": str
        }
    """
    work_dir = work_dir or os.path.dirname(wt_pdb) or "."
    
    # Get energies
    wt_energy = run_stability(wt_pdb, work_dir)
    mut_energy = run_stability(mut_pdb, work_dir)
    
    if wt_energy is None or mut_energy is None:
        return {
            "error": "Could not calculate stability",
            "wt_energy": wt_energy,
            "mut_energy": mut_energy,
            "ddg": None,
            "interpretation": "ERROR"
        }
    
    ddg = mut_energy - wt_energy
    
    # Interpret
    if ddg > 2.0:
        interpretation = "HIGHLY_DESTABILIZING"
    elif ddg > 0.5:
        interpretation = "DESTABILIZING"
    elif ddg > -0.5:
        interpretation = "NEUTRAL"
    else:
        interpretation = "STABILIZING"
    
    return {
        "wt_energy": round(wt_energy, 2),
        "mut_energy": round(mut_energy, 2),
        "ddg": round(ddg, 2),
        "interpretation": interpretation
    }


def run_buildmodel(pdb_file, mutation_code, work_dir=None):
    """
    Run FoldX BuildModel for a specific substitution mutation.
    
    Args:
        pdb_file: Path to repaired PDB
        mutation_code: e.g., "EA7V" (WT_AA + Chain + Position + MUT_AA)
        
    Returns:
        dict with DDG and interpretation
    """
    if not FOLDX_EXE:
        return {"error": "FoldX not found. Set FOLDX_EXE env var or place foldx executable in project root."}
    if not os.path.exists(pdb_file):
        return {"error": "PDB file not found"}

    pdb_name = os.path.basename(pdb_file)
    work_dir = work_dir or os.path.dirname(pdb_file) or "."

    _ensure_rotabase(work_dir)
    # Create individual_list.txt
    indiv_file = os.path.join(work_dir, "individual_list.txt")
    with open(indiv_file, 'w') as f:
        f.write(f"{mutation_code};\n")
    
    cmd = [FOLDX_EXE, "--command=BuildModel", f"--pdb={pdb_name}", "--mutant-file=individual_list.txt"]
    
    try:
        result = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True, timeout=600)
        
        # Find Dif_*.fxout file
        dif_files = [f for f in os.listdir(work_dir) if f.startswith("Dif_") and f.endswith(".fxout")]
        
        if dif_files:
            with open(os.path.join(work_dir, dif_files[0]), 'r') as f:
                content = f.read()
                # Parse DDG from file (format varies)
                for line in content.split('\n'):
                    if mutation_code in line or 'total' in line.lower():
                        parts = line.split()
                        for part in parts:
                            try:
                                ddg = float(part)
                                if -50 < ddg < 50:  # Sanity check
                                    return {
                                        "ddg": round(ddg, 2),
                                        "interpretation": "DESTABILIZING" if ddg > 0.5 else "NEUTRAL"
                                    }
                            except ValueError:
                                continue
        
        return {"error": "Could not parse BuildModel output", "ddg": None}
        
    except subprocess.TimeoutExpired:
        return {"error": "BuildModel timed out"}
    except Exception as e:
        return {"error": str(e)}


def repair_pdb(pdb_file, work_dir=None):
    """
    Run FoldX RepairPDB to optimize structure.

    Returns:
        str: Path to repaired PDB, or None if failed
    """
    if not FOLDX_EXE:
        print("FoldX not found. Set FOLDX_EXE env var or place foldx executable in project root.")
        return None
    if not os.path.exists(pdb_file):
        return None

    pdb_name = os.path.basename(pdb_file)
    work_dir = work_dir or os.path.dirname(pdb_file) or "."

    # Copy PDB to work dir
    if os.path.dirname(pdb_file) != work_dir:
        shutil.copy(pdb_file, os.path.join(work_dir, pdb_name))

    _ensure_rotabase(work_dir)
    cmd = [FOLDX_EXE, "--command=RepairPDB", f"--pdb={pdb_name}"]
    
    try:
        result = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True, timeout=1800)
        
        # Expected output: PDBname_Repair.pdb
        repaired_name = pdb_name.replace('.pdb', '_Repair.pdb')
        repaired_path = os.path.join(work_dir, repaired_name)
        
        if os.path.exists(repaired_path):
            return repaired_path
        
        return None
        
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        print(f"RepairPDB error: {e}")
        return None


# Test
if __name__ == "__main__":
    WT = r"C:\Users\sabat\OneDrive\Desktop\Alphafold\alphafold_viewer\data\reference\P68871\P68871.pdb"
    MUT = r"C:\Users\sabat\OneDrive\Desktop\Alphafold\test_b4a43_0\test_b4a43_0_unrelaxed_rank_001_alphafold2_ptm_model_5_seed_000.pdb"
    
    print("Testing FoldX Runner...")
    print("\n1. Testing Two-State Stability...")
    result = run_two_state_stability(WT, MUT)
    print(f"Result: {result}")
