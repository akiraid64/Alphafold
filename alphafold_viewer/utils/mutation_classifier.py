"""
Mutation Classifier - Detects and classifies mutation types
Types: Substitution, Deletion, Insertion, Frameshift, Duplication
"""

from Bio.PDB import PDBParser
from Bio.SeqUtils import seq1
from Bio import pairwise2

def extract_sequence_from_pdb(pdb_file):
    """Extract amino acid sequence from PDB file"""
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("protein", pdb_file)
    
    sequence = []
    for model in structure:
        for chain in model:
            for residue in chain:
                if residue.id[0] != " ":
                    continue
                try:
                    aa = seq1(residue.get_resname())
                    sequence.append(aa)
                except:
                    continue
            break
        break
    
    return "".join(sequence)


def classify_mutation(wt_seq, mut_seq):
    """
    Classify mutation type based on sequence comparison.
    
    Returns:
        tuple: (mutation_type, mutations_list, details)
        
        mutation_type: "Substitution" | "Deletion" | "Insertion" | "Frameshift" | "Duplication" | "Identical"
        mutations_list: List of mutation codes (e.g., ["E7V"])
        details: Dict with additional info
    """
    
    len_wt = len(wt_seq)
    len_mut = len(mut_seq)
    
    # Check for identical sequences
    if wt_seq == mut_seq:
        return "Identical", [], {"message": "Sequences are identical"}
    
    # Check for duplications (repeated patterns)
    if len_mut > len_wt * 1.5:  # Mutant significantly longer
        # Check for repeat patterns
        for i in range(3, 20):
            pattern = mut_seq[:i]
            if mut_seq.count(pattern) > wt_seq.count(pattern) + 2:
                return "Duplication", [], {
                    "pattern": pattern,
                    "repeat_count": mut_seq.count(pattern),
                    "message": f"Repeat expansion detected: {pattern} x{mut_seq.count(pattern)}"
                }
    
    # Same length - likely substitution(s)
    if len_wt == len_mut:
        mutations = []
        consecutive_mismatches = 0
        max_consecutive = 0
        
        for i in range(len_wt):
            if wt_seq[i] != mut_seq[i]:
                mutations.append({
                    "code": f"{wt_seq[i]}{i+1}{mut_seq[i]}",
                    "position": i + 1,
                    "wt_aa": wt_seq[i],
                    "mut_aa": mut_seq[i],
                    "type": "SUB"
                })
                consecutive_mismatches += 1
                max_consecutive = max(max_consecutive, consecutive_mismatches)
            else:
                consecutive_mismatches = 0
        
        # Frameshift if 5+ consecutive mismatches
        if max_consecutive >= 5:
            return "Frameshift", mutations, {
                "consecutive_mismatches": max_consecutive,
                "message": "Sequence scrambled after mutation point"
            }
        
        # Regular substitution(s)
        mutation_codes = [m["code"] for m in mutations]
        return "Substitution", mutation_codes, {
            "count": len(mutations),
            "mutations": mutations
        }
    
    # Different lengths - deletion or insertion
    diff = len_wt - len_mut
    
    if diff > 0:  # Mutant is shorter = Deletion
        # Align to find deletion positions
        alignments = pairwise2.align.globalms(wt_seq, mut_seq, 2, -1, -10, -0.5)
        
        if alignments:
            aln_wt = alignments[0].seqA
            aln_mut = alignments[0].seqB
            
            deletions = []
            wt_pos = 0
            
            for i in range(len(aln_wt)):
                if aln_wt[i] != '-':
                    wt_pos += 1
                    if aln_mut[i] == '-':
                        deletions.append({
                            "code": f"{aln_wt[i]}{wt_pos}del",
                            "position": wt_pos,
                            "aa": aln_wt[i],
                            "type": "DEL"
                        })
            
            mutation_codes = [d["code"] for d in deletions]
            return "Deletion", mutation_codes, {
                "count": len(deletions),
                "length_diff": diff,
                "mutations": deletions
            }
    
    else:  # Mutant is longer = Insertion
        alignments = pairwise2.align.globalms(wt_seq, mut_seq, 2, -1, -10, -0.5)
        
        if alignments:
            aln_wt = alignments[0].seqA
            aln_mut = alignments[0].seqB
            
            insertions = []
            wt_pos = 0
            
            for i in range(len(aln_wt)):
                if aln_wt[i] != '-':
                    wt_pos += 1
                if aln_wt[i] == '-':
                    insertions.append({
                        "code": f"{wt_pos}_ins_{aln_mut[i]}",
                        "position": wt_pos,
                        "aa": aln_mut[i],
                        "type": "INS"
                    })
            
            mutation_codes = [ins["code"] for ins in insertions]
            return "Insertion", mutation_codes, {
                "count": len(insertions),
                "length_diff": abs(diff),
                "mutations": insertions
            }
    
    return "Unknown", [], {"message": "Could not classify mutation"}


def get_mutation_summary(wt_pdb, mut_pdb):
    """
    High-level function to classify mutations between two PDB files.
    
    Returns dict with:
        - wt_length, mut_length
        - mutation_type
        - mutations (list of codes)
        - details
    """
    wt_seq = extract_sequence_from_pdb(wt_pdb)
    mut_seq = extract_sequence_from_pdb(mut_pdb)
    
    if not wt_seq or not mut_seq:
        return {
            "error": "Could not extract sequences from PDB files",
            "wt_length": len(wt_seq) if wt_seq else 0,
            "mut_length": len(mut_seq) if mut_seq else 0
        }
    
    mutation_type, mutations, details = classify_mutation(wt_seq, mut_seq)
    
    return {
        "wt_length": len(wt_seq),
        "mut_length": len(mut_seq),
        "wt_sequence": wt_seq[:50] + "..." if len(wt_seq) > 50 else wt_seq,
        "mut_sequence": mut_seq[:50] + "..." if len(mut_seq) > 50 else mut_seq,
        "mutation_type": mutation_type,
        "mutations": mutations,
        "details": details
    }


# Test
if __name__ == "__main__":
    WT = r"C:\Users\sabat\OneDrive\Desktop\Alphafold\alphafold_viewer\data\reference\P68871\P68871.pdb"
    MUT = r"C:\Users\sabat\OneDrive\Desktop\Alphafold\test_b4a43_0\test_b4a43_0_unrelaxed_rank_001_alphafold2_ptm_model_5_seed_000.pdb"
    
    print("Testing Mutation Classifier...")
    result = get_mutation_summary(WT, MUT)
    
    print(f"\nWT Length: {result['wt_length']}")
    print(f"Mut Length: {result['mut_length']}")
    print(f"Mutation Type: {result['mutation_type']}")
    print(f"Mutations: {result['mutations']}")
    print(f"Details: {result['details']}")
