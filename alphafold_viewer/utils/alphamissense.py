"""
AlphaMissense Lookup - Query pathogenicity scores
"""

import requests


def lookup_score(uniprot_id, mutation_code, position):
    """
    Query AlphaMissense API for pathogenicity score.
    
    Args:
        uniprot_id: e.g., "P68871"
        mutation_code: e.g., "E7V"
        position: Residue position (1-indexed)
        
    Returns:
        dict: {
            "score": float (0-1),
            "classification": "PATHOGENIC" | "BENIGN" | "AMBIGUOUS" | "NOT_FOUND",
            "raw_data": dict from API
        }
    """
    # Extract the mutant amino acid (last character)
    mut_aa = mutation_code[-1] if mutation_code else None
    
    if not mut_aa:
        return {"score": None, "classification": "NOT_FOUND", "error": "Invalid mutation code"}
    
    url = f"https://alphamissense.hegelab.org/hotspotapi?uid={uniprot_id}&resi={position}"
    
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        
        # Parse response
        pathogenic_list = str(data.get('pathogenic_all', ''))
        benign_list = str(data.get('benign_all', ''))
        ambiguous_list = str(data.get('ambiguous_all', ''))
        mean_score = data.get('mean_all', None)
        
        # Determine classification
        if mut_aa in pathogenic_list:
            score = 0.9
            classification = "PATHOGENIC"
        elif mut_aa in benign_list:
            score = 0.1
            classification = "BENIGN"
        elif mut_aa in ambiguous_list:
            score = 0.5
            classification = "AMBIGUOUS"
        elif mean_score is not None:
            score = mean_score
            if score > 0.564:
                classification = "PATHOGENIC"
            elif score < 0.340:
                classification = "BENIGN"
            else:
                classification = "AMBIGUOUS"
        else:
            score = None
            classification = "NOT_FOUND"
        
        return {
            "score": round(score, 4) if score else None,
            "classification": classification,
            "position_aa": data.get('aa'),
            "raw_data": data
        }
        
    except requests.exceptions.Timeout:
        return {"score": None, "classification": "TIMEOUT", "error": "API timeout"}
    except Exception as e:
        return {"score": None, "classification": "ERROR", "error": str(e)}


def batch_lookup(uniprot_id, mutations):
    """
    Look up multiple mutations at once.
    
    Args:
        uniprot_id: UniProt ID
        mutations: List of dicts with {code, position}
        
    Returns:
        List of results
    """
    results = []
    
    for mut in mutations[:20]:  # Limit to 20 to avoid API overload
        code = mut.get('code', '')
        position = mut.get('position', 0)
        
        result = lookup_score(uniprot_id, code, position)
        result['mutation_code'] = code
        results.append(result)
    
    return results


# Test
if __name__ == "__main__":
    print("Testing AlphaMissense Lookup...")
    
    # Test E7V (Sickle Cell)
    result = lookup_score("P68871", "E7V", 7)
    print(f"\nE7V (Sickle Cell):")
    print(f"  Score: {result['score']}")
    print(f"  Classification: {result['classification']}")
