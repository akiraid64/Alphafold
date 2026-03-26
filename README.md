# AlphaFold Mutation Analysis Toolkit

**Predict whether any mutation — including novel, never-before-seen variants — is harmful to a protein, and explain why.**

This platform doesn't rely on databases of known mutations. It uses physics-based simulation (FoldX) and deep learning (AlphaMissense) to assess mutations from first principles. Give it a wild-type and mutant sequence for any protein, and it will tell you:
- **Is this mutation pathogenic?** (AlphaMissense pathogenicity score)
- **Does it destabilize the protein?** (FoldX DDG energy calculation)
- **Where does the damage occur?** (3D structural comparison showing exactly which residues shift)
- **How confident should we be?** (Combined multi-evidence risk assessment)

This works on mutations that have never been clinically observed — no prior case reports or literature needed.

No existing open-source tool combines all three of these methods (AlphaFold2 + FoldX + AlphaMissense) into a single automated pipeline.

| Existing Tool | What It Does | What It's Missing |
|---|---|---|
| **Missense3D** | 3D structural analysis of missense variants | No FoldX, no AlphaMissense, own geometric checks only |
| **ProteinGym** | Benchmarks ~50 variant effect predictors | Not an analysis tool — it's a benchmark dataset, no web viewer |
| **DynaMut / DynaMut2** | Stability prediction with visualization | Own ENM model (not FoldX), no AlphaMissense |
| **OpenCRAVAT** | Modular variant annotation framework | No one has built an AlphaFold+FoldX+AlphaMissense integration |
| **MutFold** | AlphaFold + FoldX integration | No AlphaMissense, not a polished web platform |
| **This project** | AlphaFold2 + FoldX + AlphaMissense + 3D visualization + automated mutation routing | - |

### Why combining these three is powerful

- **AlphaMissense** (Cheng et al., *Science* 2023) gives an instant pathogenicity score (0-1) for any amino acid substitution — but cannot explain *why* a variant is damaging
- **FoldX** provides the biophysical mechanism — which energy terms are disrupted (van der Waals clashes, solvation, electrostatics) — but doesn't directly predict clinical pathogenicity
- **AlphaFold2 3D structures** show *where* the mutation sits (buried core vs. surface vs. active site), which neither score alone conveys

A variant might be flagged "ambiguous" by AlphaMissense while FoldX shows a clear destabilizing DDG > 2 kcal/mol — or vice versa. **Combined multi-evidence interpretation is the direction ACMG clinical guidelines (PP3/BP4 criteria) are moving.**

### The mutation-type router solves an under-addressed problem

Most existing tools handle **only missense (substitution) variants**. AlphaMissense is substitution-only by design. FoldX can handle deletions and insertions but requires different commands. This project's analysis router automatically detects the mutation type and selects the right tool combination — a workflow step that researchers currently do manually.

## Features

- **Automated Mutation Routing** — Detects mutation type (substitution, deletion, insertion, frameshift, duplication) and selects the right analysis tools automatically
- **FoldX Stability Engine** — DDG calculations to quantify how a mutation destabilizes the protein's 3D structure
- **AlphaMissense Pathogenicity** — Instant pathogenicity scoring for amino acid substitutions
- **Structural Comparison** — RMSD and per-residue distance calculations between wild-type and mutant structures via TM-align
- **Combined Risk Assessment** — Cross-references FoldX stability, AlphaMissense pathogenicity, and structural deviation to produce a unified verdict
- **Interactive 3D Visualization** — Compare wild-type vs mutant protein structures side-by-side in the browser

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

### Start the Server

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

## How It Works — The Analysis Pipeline

The platform runs a 4-phase pipeline. This is not a simple wrapper around FoldX — it implements custom scoring formulas, a two-state energy comparison method, an approximate TM-score calculation, and a multi-evidence verdict system.

### Phase 1: Mutation Classification

The classifier extracts amino acid sequences from both PDB structures using BioPython, then runs pairwise sequence alignment with custom scoring parameters:

```
Alignment scoring: match = +2, mismatch = -1, gap_open = -10, gap_extend = -0.5
```

Based on the alignment, it classifies the mutation:

| Detection Rule | Classification |
|---|---|
| Sequences identical | **Identical** (no analysis needed) |
| Same length, mismatches at isolated positions | **Substitution** (e.g., E6V) |
| Same length, 5+ consecutive mismatches | **Frameshift** (reading frame destroyed) |
| Mutant shorter than wild-type | **Deletion** (e.g., F508del) |
| Mutant longer than wild-type | **Insertion** |
| Mutant > 1.5x length + repeat pattern detected | **Duplication** (repeat expansion) |

### Phase 2: Tool Routing

Each mutation type triggers a different combination of analysis tools:

```
Substitution  → AlphaMissense + FoldX + Structural Comparison
Deletion      → FoldX + Structural Comparison
Insertion     → FoldX + Structural Comparison
Frameshift    → AUTO_FAIL (loss of function)
Duplication   → AUTO_FAIL (toxic aggregation risk)
```

This is important because AlphaMissense only works on single amino acid substitutions, and FoldX's `BuildModel` command only handles substitutions. For deletions and insertions, the platform uses a **custom two-state stability method** instead (see below).

### Phase 3: Custom Scoring Formulas

#### FoldX Two-State Stability (custom method)

Standard FoldX `BuildModel` only works for substitutions. For deletions, insertions, and other structural mutations, this project implements a **two-state energy comparison**:

```
ΔG_wt  = FoldX Stability(wild-type PDB)
ΔG_mut = FoldX Stability(mutant PDB)

ΔΔG = ΔG_mut - ΔG_wt
```

Where `ΔG` is the Gibbs free energy of folding (kcal/mol). A positive ΔΔG means the mutation makes the protein less stable. The platform applies a **5-tier interpretation scale** (more granular than FoldX's default output):

| ΔΔG Range (kcal/mol) | Interpretation | Severity |
|---|---|---|
| ΔΔG > 2.0 | Highly Destabilizing | Critical |
| ΔΔG > 1.6 | Destabilizing | High |
| ΔΔG > 0.5 | Mildly Destabilizing | Moderate |
| -0.5 < ΔΔG < 0.5 | Neutral | None |
| ΔΔG < -0.5 | Stabilizing | None |

The **1.6 kcal/mol threshold** is significant — it corresponds to the empirically validated cutoff used in the literature for distinguishing pathogenic from benign variants based on thermodynamic stability (Gerasimavicius et al., 2020).

#### TM-score Approximation (no external binary needed)

Instead of requiring the TM-align binary, the platform implements the **Zhang & Skolnick (2004) TM-score formula** directly using BioPython's structural superposition:

```
d₀ = 1.24 × ∛(L_target - 15) - 1.8

TM-score = (1 / L_target) × Σᵢ [ 1 / (1 + (dᵢ / d₀)²) ]
```

Where:
- `L_target` = number of residues in the target protein
- `dᵢ` = distance (Å) between the i-th pair of aligned Cα atoms after superposition
- `d₀` = length-dependent normalization factor

The TM-score ranges from 0 to 1. The platform interprets it as:

| TM-score | Structural Verdict |
|---|---|
| ≥ 0.95 | Structure Intact |
| 0.50 – 0.95 | Minor Changes |
| < 0.50 | Significant Changes |

Per-residue deviations above **2.0 Å** are flagged as high-deviation regions — these pinpoint exactly where the mutation disrupts the backbone.

#### Sequence Identity

```
Sequence Identity (%) = ((L_wt - N_mutations) / L_wt) × 100
```

### Phase 4: Multi-Evidence Verdict

The final pathogenicity call combines AlphaMissense and FoldX using a custom decision matrix:

```
AlphaMissense = PATHOGENIC  AND  FoldX ΔΔG > 1.6  →  PATHOGENIC
AlphaMissense = PATHOGENIC  AND  FoldX ΔΔG ≤ 1.6  →  LIKELY_PATHOGENIC
AlphaMissense ≠ PATHOGENIC  AND  FoldX ΔΔG > 1.6  →  LIKELY_PATHOGENIC
AlphaMissense ≠ PATHOGENIC  AND  FoldX ΔΔG > 0.5  →  UNCERTAIN
Neither flagged                                     →  BENIGN
```

This mirrors the **ACMG/AMP PP3/BP4 evidence combination framework** — using multiple independent lines of computational evidence to reach a stronger conclusion than either tool alone.

