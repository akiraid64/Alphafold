# AlphaFold Mutation Analysis Toolkit

A protein mutation analysis platform that combines **AlphaFold2** structure predictions, **FoldX** stability calculations, and **AlphaMissense** pathogenicity scores to assess the impact of genetic mutations on protein structure and function.

## Features

- **3D Protein Viewer** — Interactive web-based viewer for comparing wild-type vs mutant protein structures
- **Mutation Classification** — Automatic detection of substitutions, deletions, insertions, frameshifts, and duplications
- **FoldX Stability Analysis** — DDG (change in free energy) calculations to predict if a mutation destabilizes the protein
- **AlphaMissense Integration** — Pathogenicity score lookup for amino acid substitutions
- **Structural Comparison** — RMSD and per-residue distance calculations between structures via TM-align
- **Multi-tool Routing** — Automatically selects which analysis tools are appropriate for each mutation type

## Project Structure

```
Alphafold/
├── alphafold_viewer/           # FastAPI web application
│   ├── server.py               # Main server (API endpoints)
│   ├── templates/              # HTML templates (3D viewer, mutation analysis)
│   ├── static/                 # CSS and JavaScript
│   ├── utils/                  # Analysis modules
│   │   ├── foldx_runner.py     # FoldX wrapper (auto-detects FoldX location)
│   │   ├── alphamissense.py    # AlphaMissense API client
│   │   ├── mutation_classifier.py  # Mutation type detection
│   │   ├── analysis_router.py  # Routes mutations to appropriate tools
│   │   ├── structure_compare.py    # RMSD/distance calculations
│   │   └── pdb_combiner.py     # Superposition of PDB structures
│   └── data/reference/         # Reference protein structures (P68871, P35557)
│
├── alphafold2.ipynb            # AlphaFold2 prediction notebook (ColabFold)
├── test_b4a43_0/               # AlphaFold2 prediction output (HBB mutant)
├── *.fasta                     # Input sequences (CFTR, HBB wild-type/mutant)
└── .gitignore
```

## Prerequisites

- **Python 3.10+**
- **FoldX** (see below)
- **BioPython** — `pip install biopython`
- **FastAPI + Uvicorn** — `pip install fastapi uvicorn`
- **httpx** — `pip install httpx`
- **NumPy** — `pip install numpy`

### FoldX Setup

FoldX is proprietary software and **cannot be distributed with this repository**. You must obtain it separately:

1. Register at [https://foldxsuite.crg.eu/](https://foldxsuite.crg.eu/) (free for academic use)
2. Download the FoldX executable and `rotabase.txt`
3. Place both files in the project root directory

The app **auto-detects** FoldX — no config editing needed. It searches for FoldX in this order:

1. `FOLDX_EXE` environment variable (set to full path of the executable)
2. Any `foldx*.exe` or `foldx` binary in the project root
3. `foldx` on your system PATH

`rotabase.txt` is found automatically if placed next to the FoldX executable or in the project root. You can also set `FOLDX_DIR` to point to the directory containing it.

## Usage

### Start the Viewer

```bash
cd alphafold_viewer
python server.py
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

### Generate AlphaFold2 Predictions

Use `alphafold2.ipynb` on Google Colab with ColabFold to generate structure predictions, then place the output in the project directory for analysis.

## Proteins Studied

| Protein | UniProt | Mutation | Disease |
|---------|---------|----------|---------|
| Hemoglobin subunit beta (HBB) | P68871 | E6V | Sickle cell disease |
| CFTR | P13569 | DeltaF508 | Cystic fibrosis |
| Glucokinase (GCK) | P35557 | Various | MODY2 diabetes |

## How It Works

1. **Input**: Wild-type and mutant FASTA sequences or PDB structures
2. **Classification**: The mutation classifier compares sequences to determine mutation type
3. **Routing**: The analysis router selects appropriate tools based on mutation type:
   - Substitutions: AlphaMissense + FoldX + structural comparison
   - Deletions/Insertions: FoldX stability + structural comparison
   - Frameshifts/Duplications: Classification only (tools not applicable)
4. **Output**: DDG values, pathogenicity scores, RMSD, and a combined risk assessment

## Why This Matters

**No existing open-source tool integrates all three of these analysis methods (AlphaFold2 + FoldX + AlphaMissense) into a single web-based viewer.** Here is how this project differs from existing tools:

| Existing Tool | What It Does | What It's Missing |
|---|---|---|
| **Missense3D** | 3D structural analysis of missense variants | No FoldX, no AlphaMissense, uses its own geometric checks only |
| **ProteinGym** | Benchmarks ~50 variant effect predictors (including FoldX and AlphaMissense) | Not an analysis tool — it's a benchmark dataset, no web viewer |
| **DynaMut / DynaMut2** | Stability prediction with visualization | Uses its own ENM model (not FoldX), no AlphaMissense |
| **OpenCRAVAT** | Modular variant annotation framework | Could theoretically add plugins, but no one has built an AlphaFold+FoldX+AlphaMissense integration with 3D viewing |
| **MutFold** | AlphaFold + FoldX integration | No AlphaMissense, not a polished web platform |
| **This project** | AlphaFold2 structures + FoldX stability + AlphaMissense pathogenicity + 3D viewer + mutation routing | - |

### Why combining these three specifically is powerful

- **AlphaMissense** (Cheng et al., *Science* 2023) gives an instant pathogenicity score (0-1) for any single amino acid substitution — but it cannot explain *why* a variant is damaging
- **FoldX** provides the biophysical mechanism — which energy terms are disrupted (van der Waals clashes, solvation, electrostatics) — but it doesn't directly predict clinical pathogenicity
- **AlphaFold2 3D structures** show *where* the mutation sits (buried core vs. surface vs. active site), which neither score alone conveys

A variant might be flagged "ambiguous" by AlphaMissense while FoldX shows a clear destabilizing DDG > 2 kcal/mol — or vice versa. **Combined multi-evidence interpretation is the direction ACMG clinical guidelines (PP3/BP4 criteria) are moving**, and clinicians currently have to visit 3-5 separate websites to gather this evidence.

### The mutation-type router is an under-addressed problem

Most existing tools handle **only missense (substitution) variants**. AlphaMissense is substitution-only by design. FoldX can handle deletions and insertions but requires different commands. This project's analysis router automatically detects the mutation type and selects the right tool combination — a workflow step that researchers currently do manually.
