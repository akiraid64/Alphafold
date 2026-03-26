"""
Analysis Router v3.0 - Complete Mutation Analysis Pipeline
Routes mutations to appropriate tools based on type and returns comprehensive results.
"""

from .mutation_classifier import get_mutation_summary
from .foldx_runner import run_two_state_stability, run_stability
from .alphamissense import lookup_score

# Tool routing table per mutation type
TOOL_ROUTING = {
    "Substitution": {"alphamissense": True, "foldx": True, "tmalign": True},
    "Deletion": {"alphamissense": False, "foldx": True, "tmalign": True},
    "Insertion": {"alphamissense": False, "foldx": True, "tmalign": True},
    "Frameshift": {"alphamissense": False, "foldx": False, "tmalign": False},
    "Duplication": {"alphamissense": False, "foldx": False, "tmalign": False},
    "Identical": {"alphamissense": False, "foldx": False, "tmalign": False}
}


def route_analysis(wt_pdb, mut_pdb, uniprot_id):
    """
    Main routing function - classifies mutation and runs appropriate tools.
    Returns comprehensive JSON for frontend display.
    """
    
    # =============================================
    # PHASE 1: SCANNER - Mutation Detection
    # =============================================
    classification = get_mutation_summary(wt_pdb, mut_pdb)
    
    if "error" in classification:
        return {
            "status": "ERROR",
            "error": classification["error"],
            "scan_results": None,
            "pipeline_decision": "FAILED",
            "results": {}
        }
    
    mutation_type = classification["mutation_type"]
    mutations = classification.get("mutations", [])
    details = classification.get("details", {})
    
    # Calculate sequence identity
    wt_len = classification.get("wt_length", 0)
    mut_len = classification.get("mut_length", 0)
    mutation_count = details.get("count", len(mutations)) if details else len(mutations)
    seq_identity = ((wt_len - mutation_count) / wt_len * 100) if wt_len > 0 else 0
    
    # Build scan results
    scan_results = {
        "detected_mutation": mutations[0] if mutations else None,
        "mutation_list": mutations,
        "type": mutation_type,
        "sequence_identity": f"{seq_identity:.1f}%",
        "wt_length": wt_len,
        "mut_length": mut_len
    }
    
    # =============================================
    # PHASE 2: CLASSIFIER - Route to Tools
    # =============================================
    routing = TOOL_ROUTING.get(mutation_type, TOOL_ROUTING["Identical"])
    
    # Check for critical failures
    if mutation_type == "Frameshift":
        return {
            "status": "CRITICAL_FAILURE",
            "mutation_type": mutation_type,
            "scan_results": scan_results,
            "pipeline_decision": "AUTO_FAIL",
            "biological_mechanism": "Genetic Information Loss",
            "ui_display": {
                "message": "Reading frame destroyed. Protein synthesis failed.",
                "color": "red"
            },
            "results": {
                "alphamissense": {"active": False, "reason": "Not applicable for frameshifts"},
                "foldx": {"active": False, "reason": "Not applicable for frameshifts"},
                "tmalign": {"active": False, "reason": "Not applicable for frameshifts"}
            },
            "verdict": "LOSS_OF_FUNCTION",
            "verdict_class": "danger"
        }
    
    if mutation_type == "Duplication":
        return {
            "status": "CRITICAL_FAILURE",
            "mutation_type": mutation_type,
            "scan_results": scan_results,
            "pipeline_decision": "AUTO_FAIL",
            "biological_mechanism": "Toxic Aggregation",
            "ui_display": {
                "message": "Repeat expansion detected. High risk of toxic clumping.",
                "color": "red"
            },
            "results": {
                "alphamissense": {"active": False, "reason": "Not applicable for duplications"},
                "foldx": {"active": False, "reason": "Not applicable for duplications"},
                "tmalign": {"active": False, "reason": "Not applicable for duplications"}
            },
            "verdict": "LIKELY_PATHOGENIC",
            "verdict_class": "danger"
        }
    
    if mutation_type == "Identical":
        return {
            "status": "SUCCESS",
            "mutation_type": mutation_type,
            "scan_results": scan_results,
            "pipeline_decision": "NO_MUTATION",
            "results": {
                "alphamissense": {"active": False, "reason": "No mutation detected"},
                "foldx": {"active": False, "reason": "No mutation detected"},
                "tmalign": {"active": False, "reason": "No mutation detected"}
            },
            "verdict": "NO_MUTATION",
            "verdict_class": "success"
        }
    
    # =============================================
    # PHASE 3: TOOL EXECUTION
    # =============================================
    results = {}
    
    # --- TOOL A: AlphaMissense ---
    if routing["alphamissense"] and mutations:
        try:
            mut_code = mutations[0]  # e.g., "E7V"
            position = int(''.join(filter(str.isdigit, mut_code)))
            am_result = lookup_score(uniprot_id, mut_code, position)
            
            score = am_result.get("score")
            am_class = am_result.get("classification", "UNKNOWN")
            
            results["alphamissense"] = {
                "active": True,
                "status": "Active",
                "score": score,
                "class": am_class,
                "verdict": "Pathogenic" if am_class == "PATHOGENIC" else "Benign" if am_class == "BENIGN" else "Unknown",
                "reason": "Evolutionary constraint violated" if am_class == "PATHOGENIC" else "Evolutionarily tolerated"
            }
        except Exception as e:
            results["alphamissense"] = {
                "active": False,
                "status": "Error",
                "reason": str(e)
            }
    else:
        results["alphamissense"] = {
            "active": False,
            "status": "Disabled",
            "reason": f"Not applicable for {mutation_type.lower()}s"
        }
    
    # --- TOOL B: FoldX Stability ---
    if routing["foldx"]:
        try:
            foldx_result = run_two_state_stability(wt_pdb, mut_pdb)
            
            energy_wt = foldx_result.get("wt_energy")
            energy_mut = foldx_result.get("mut_energy")
            ddg = foldx_result.get("ddg")
            
            # Calculate stability verdict
            if ddg is not None:
                if ddg > 2.0:
                    stability_verdict = "Highly Destabilizing"
                    stability_class = "danger"
                elif ddg > 1.6:
                    stability_verdict = "Destabilizing"
                    stability_class = "warning"
                elif ddg > 0.5:
                    stability_verdict = "Mildly Destabilizing"
                    stability_class = "warning"
                elif ddg > -0.5:
                    stability_verdict = "Neutral"
                    stability_class = "secondary"
                else:
                    stability_verdict = "Stabilizing"
                    stability_class = "success"
            else:
                stability_verdict = "Unknown"
                stability_class = "secondary"
            
            results["foldx"] = {
                "active": True,
                "status": "Active",
                "energy_wildtype": energy_wt,
                "energy_mutant": energy_mut,
                "ddg": ddg,
                "stability_verdict": stability_verdict,
                "stability_class": stability_class,
                "reason": "Thermodynamic Destabilization" if ddg and ddg > 1.6 else "Thermodynamic Stability Maintained"
            }
        except Exception as e:
            results["foldx"] = {
                "active": False,
                "status": "Error",
                "reason": str(e)
            }
    else:
        results["foldx"] = {
            "active": False,
            "status": "Disabled",
            "reason": f"Not applicable for {mutation_type.lower()}s"
        }
    
    # --- TOOL C: TM-align (Using BioPython-based calculation) ---
    if routing["tmalign"]:
        try:
            from .structure_compare import calculate_residue_distances
            
            comparison = calculate_residue_distances(wt_pdb, mut_pdb)
            
            if "error" in comparison:
                results["tmalign"] = {
                    "active": False,
                    "status": "Error",
                    "reason": comparison["error"]
                }
            else:
                tm_score = comparison.get("tm_score", 0)
                rmsd = comparison.get("global_rmsd", 0)
                
                # Calculate structure verdict
                if tm_score >= 0.95:
                    structure_verdict = "Structure Intact"
                    structure_class = "success"
                elif tm_score >= 0.5:
                    structure_verdict = "Minor Changes"
                    structure_class = "warning"
                else:
                    structure_verdict = "Significant Changes"
                    structure_class = "danger"
                
                results["tmalign"] = {
                    "active": True,
                    "status": "Active",
                    "tm_score": tm_score,
                    "rmsd": rmsd,
                    "max_deviation": comparison.get("max_deviation", 0),
                    "n_residues": comparison.get("n_residues", 0),
                    "structure_verdict": structure_verdict,
                    "structure_class": structure_class,
                    "reason": "Backbone Topology Intact" if tm_score >= 0.5 else "Backbone Topology Disrupted"
                }
        except Exception as e:
            results["tmalign"] = {
                "active": False,
                "status": "Error",
                "reason": str(e)
            }
    else:
        results["tmalign"] = {
            "active": False,
            "status": "Disabled",
            "reason": f"Not applicable for {mutation_type.lower()}s"
        }
    
    # =============================================
    # PHASE 4: FINAL VERDICT
    # =============================================
    verdict, verdict_class, verdict_reason = calculate_final_verdict(
        mutation_type, results
    )
    
    return {
        "status": "SUCCESS",
        "mutation_type": mutation_type,
        "mutations": mutations,
        "scan_results": scan_results,
        "pipeline_decision": "RUN_ALL" if mutation_type == "Substitution" else "STRUCTURAL_ONLY",
        "results": results,
        "verdict": verdict,
        "verdict_class": verdict_class,
        "verdict_reason": verdict_reason
    }


def calculate_final_verdict(mutation_type, results):
    """Calculate the final pathogenicity verdict based on all tool results."""
    
    # Get individual tool verdicts
    am_pathogenic = (
        results.get("alphamissense", {}).get("active", False) and
        results.get("alphamissense", {}).get("class") == "PATHOGENIC"
    )
    
    foldx_result = results.get("foldx", {})
    ddg = foldx_result.get("ddg") if foldx_result.get("active") else None
    foldx_destabilizing = ddg is not None and ddg > 1.6
    
    # Decision logic
    reasons = []
    
    if am_pathogenic:
        reasons.append("AlphaMissense: Pathogenic")
    
    if foldx_destabilizing:
        reasons.append(f"FoldX: Destabilizing (ΔΔG={ddg:.2f})")
    
    # Combine verdicts
    if am_pathogenic and foldx_destabilizing:
        return "PATHOGENIC", "danger", " + ".join(reasons)
    elif am_pathogenic:
        return "LIKELY_PATHOGENIC", "danger", reasons[0]
    elif foldx_destabilizing:
        return "LIKELY_PATHOGENIC", "warning", reasons[0]
    elif ddg is not None and ddg > 0.5:
        return "UNCERTAIN", "warning", f"Mild destabilization (ΔΔG={ddg:.2f})"
    else:
        return "BENIGN", "success", "No significant pathogenic indicators"


# Test
if __name__ == "__main__":
    import json
    WT = r"C:\Users\sabat\OneDrive\Desktop\Alphafold\alphafold_viewer\data\reference\P68871\P68871.pdb"
    MUT = r"C:\Users\sabat\OneDrive\Desktop\Alphafold\test_b4a43_0\test_b4a43_0_unrelaxed_rank_001_alphafold2_ptm_model_5_seed_000.pdb"
    
    print("Testing Analysis Router v3.0...")
    result = route_analysis(WT, MUT, "P68871")
    print(json.dumps(result, indent=2))
