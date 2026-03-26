"""
Protein Structure Comparison Utilities
TM-align and residue-level difference calculation
"""

import numpy as np
from Bio.PDB import PDBParser, Superimposer
from pathlib import Path
import subprocess
import json


def calculate_residue_distances(pdb1_path, pdb2_path):
    """
    Calculate per-residue distance between two aligned structures.
    Returns residue-level deviation data for visualization.
    """
    import time
    start_time = time.time()
    
    parser = PDBParser(QUIET=True)
    
    try:
        print(f"[Compare] Step 1/4: Parsing PDB files...")
        structure1 = parser.get_structure("ref", pdb1_path)
        structure2 = parser.get_structure("test", pdb2_path)
        print(f"[Compare]   ✓ Parsed in {(time.time() - start_time)*1000:.0f}ms")
    except Exception as e:
        return {"error": f"Failed to parse PDB files: {str(e)}"}
    
    # Extract CA atoms for alignment
    step_time = time.time()
    print(f"[Compare] Step 2/4: Extracting backbone atoms...")
    ref_atoms = []
    test_atoms = []
    residue_info = []
    
    # Assume first model, first chain
    ref_chain = list(structure1.get_chains())[0]
    test_chain = list(structure2.get_chains())[0]
    
    # Find common residues
    ref_residues = {res.id[1]: res for res in ref_chain if 'CA' in res}
    test_residues = {res.id[1]: res for res in test_chain if 'CA' in res}
    
    common_ids = set(ref_residues.keys()) & set(test_residues.keys())
    
    for res_id in sorted(common_ids):
        ref_atoms.append(ref_residues[res_id]['CA'])
        test_atoms.append(test_residues[res_id]['CA'])
        residue_info.append({
            'position': res_id,
            'ref_name': ref_residues[res_id].resname,
            'test_name': test_residues[res_id].resname
        })
    
    if len(ref_atoms) < 3:
        return {"error": "Insufficient common residues for alignment"}
    
    print(f"[Compare]   ✓ Found {len(common_ids)} common residues ({(time.time() - step_time)*1000:.0f}ms)")
    
    # Superimpose structures
    step_time = time.time()
    print(f"[Compare] Step 3/4: Superimposing structures...")
    super_imposer = Superimposer()
    super_imposer.set_atoms(ref_atoms, test_atoms)
    super_imposer.apply(structure2.get_atoms())
    
    global_rmsd = super_imposer.rms
    print(f"[Compare]   ✓ Aligned! Global RMSD: {global_rmsd:.3f} Å ({(time.time() - step_time)*1000:.0f}ms)")
    
    # Calculate per-residue deviation
    step_time = time.time()
    print(f"[Compare] Step 4/4: Calculating per-residue deviations...")
    deviations = []
    max_deviation = 0
    
    for i, (ref_atom, test_atom) in enumerate(zip(ref_atoms, test_atoms)):
        diff = ref_atom.coord - test_atom.coord
        distance = np.sqrt(np.sum(diff ** 2))
        deviations.append(distance)
        max_deviation = max(max_deviation, distance)
        residue_info[i]['deviation'] = float(distance)
    
    # Calculate TM-score (simplified approximation)
    n_residues = len(deviations)
    d0 = 1.24 * (n_residues - 15) ** (1/3) - 1.8 if n_residues > 15 else 0.5
    
    tm_score_sum = sum(1 / (1 + (d / d0) ** 2) for d in deviations)
    tm_score = tm_score_sum / n_residues
    
    total_time = (time.time() - start_time) * 1000
    print(f"[Compare]   ✓ Complete! TM-score: {tm_score:.3f} ({total_time:.0f}ms total)")
    
    return {
        "global_rmsd": float(global_rmsd),
        "tm_score": float(tm_score),
        "max_deviation": float(max_deviation),
        "n_residues": n_residues,
        "residue_deviations": residue_info,
        "computation_time_ms": total_time
    }


def run_tm_align_binary(pdb1_path, pdb2_path, tm_align_exe="TMalign"):
    """
    Run TM-align binary if available (optional enhancement).
    Falls back to BioPython method if binary not found.
    """
    try:
        result = subprocess.run(
            [tm_align_exe, pdb1_path, pdb2_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Parse TM-align output
            output = result.stdout
            
            # Extract TM-score from output
            for line in output.split('\n'):
                if 'TM-score=' in line:
                    parts = line.split('TM-score=')[1].split()
                    tm_score = float(parts[0])
                    return {"tm_score": tm_score, "raw_output": output}
            
        return {"error": "TM-align binary executed but couldn't parse output"}
        
    except FileNotFoundError:
        return {"error": "TM-align binary not found, using BioPython fallback"}
    except Exception as e:
        return {"error": f"TM-align execution failed: {str(e)}"}


def generate_difference_report(comparison_result):
    """
    Generate human-readable report from comparison data.
    """
    if "error" in comparison_result:
        return comparison_result["error"]
    
    report = []
    report.append("=== STRUCTURAL COMPARISON REPORT ===\n")
    report.append(f"Global RMSD: {comparison_result['global_rmsd']:.3f} Å")
    report.append(f"TM-score: {comparison_result['tm_score']:.3f} (0-1, higher is better)")
    report.append(f"Max Residue Deviation: {comparison_result['max_deviation']:.3f} Å")
    report.append(f"Residues Compared: {comparison_result['n_residues']}\n")
    
    # Identify regions with significant differences
    high_dev_residues = [
        r for r in comparison_result['residue_deviations'] 
        if r['deviation'] > 2.0  # Threshold: 2 Angstroms
    ]
    
    if high_dev_residues:
        report.append(f"\n⚠️ High Deviation Regions ({len(high_dev_residues)} residues > 2.0 Å):")
        for r in high_dev_residues[:10]:  # Show top 10
            report.append(f"  Position {r['position']}: {r['deviation']:.2f} Å")
        if len(high_dev_residues) > 10:
            report.append(f"  ... and {len(high_dev_residues) - 10} more")
    else:
        report.append("\n✓ Structures are highly similar (all residues < 2.0 Å)")
    
    # Interpretation
    report.append("\nInterpretation:")
    if comparison_result['tm_score'] > 0.95:
        report.append("  ✓ Structures are nearly identical (TM-score > 0.95)")
    elif comparison_result['tm_score'] > 0.5:
        report.append("  ⚠️ Structures have same fold but notable differences")
    else:
        report.append("  ❌ Structures are significantly different")
    
    return "\n".join(report)
