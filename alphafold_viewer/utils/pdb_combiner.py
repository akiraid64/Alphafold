"""
Generate combined PDB file with superimposed structures
Shows original + mutated structures with deviation coloring
"""

from Bio.PDB import PDBParser, PDBIO, Superimposer, Select
import numpy as np


def identify_mutations(ref_structure, test_structure):
    """
    Compare sequences to find mutation positions.
    Returns list of (position, ref_aa, test_aa)
    """
    mutations = []
    
    ref_chain = list(ref_structure.get_chains())[0]
    test_chain = list(test_structure.get_chains())[0]
    
    ref_residues = {res.id[1]: res for res in ref_chain if res.id[0] == ' '}
    test_residues = {res.id[1]: res for res in test_chain if res.id[0] == ' '}
    
    common_ids = set(ref_residues.keys()) & set(test_residues.keys())
    
    for res_id in sorted(common_ids):
        ref_res = ref_residues[res_id]
        test_res = test_residues[res_id]
        
        if ref_res.resname != test_res.resname:
            mutations.append({
                'position': res_id,
                'ref_aa': ref_res.resname,
                'test_aa': test_res.resname
            })
    
    return mutations


def create_superposed_pdb(ref_pdb_path, test_pdb_path, output_path, deviation_data):
    """
    Create a combined PDB with:
    - Chain A: Reference (original)
    - Chain B: Test (mutated, aligned)
    - B-factors set to deviation values for coloring
    """
    parser = PDBParser(QUIET=True)
    
    # Load structures
    ref_structure = parser.get_structure("ref", ref_pdb_path)
    test_structure = parser.get_structure("test", test_pdb_path)
    
    # Get chains
    ref_chain = list(ref_structure.get_chains())[0]
    test_chain = list(test_structure.get_chains())[0]
    
    # Prepare atoms for alignment
    ref_atoms = []
    test_atoms = []
    ref_residues = {res.id[1]: res for res in ref_chain if 'CA' in res}
    test_residues = {res.id[1]: res for res in test_chain if 'CA' in res}
    
    common_ids = sorted(set(ref_residues.keys()) & set(test_residues.keys()))
    
    for res_id in common_ids:
        ref_atoms.append(ref_residues[res_id]['CA'])
        test_atoms.append(test_residues[res_id]['CA'])
    
    # Superimpose
    super_imposer = Superimposer()
    super_imposer.set_atoms(ref_atoms, test_atoms)
    super_imposer.apply(test_structure.get_atoms())
    
    # Create deviation lookup
    deviation_map = {r['position']: r['deviation'] for r in deviation_data}
    
    # Identify mutations
    mutations = identify_mutations(ref_structure, test_structure)
    mutation_positions = {m['position'] for m in mutations}
    
    # Rename chains
    ref_chain.id = 'A'
    test_chain.id = 'B'
    
    # Set B-factors to deviations for both chains
    for chain in [ref_chain, test_chain]:
        for residue in chain:
            res_id = residue.id[1]
            deviation = deviation_map.get(res_id, 0.0)
            
            # Normalize deviation to 0-100 for B-factor (0=green, 100=red)
            # Scale: 0-3 Å -> 0-100
            b_factor = min(deviation / 3.0 * 100, 100)
            
            for atom in residue:
                atom.set_bfactor(b_factor)
    
    # Create new structure with both chains
    class CombinedSelect(Select):
        def accept_model(self, model):
            return model.id == 0
    
    # Save combined PDB
    io = PDBIO()
    io.set_structure(ref_structure[0])  # Start with ref model
    
    # Add test chain to ref model
    ref_structure[0].add(test_chain)
    
    io.save(output_path, CombinedSelect())
    
    # Generate report
    report = {
        'output_file': output_path,
        'mutations': mutations,
        'num_mutations': len(mutations),
        'chain_a': 'Reference (Original)',
        'chain_b': 'Test (Mutated, Aligned)',
        'coloring': 'B-factor = deviation (Å), scaled 0-100',
        'interpretation': 'Use PyMOL/Mol* to view: spectrum b, chain A opaque, chain B transparent'
    }
    
    return report
