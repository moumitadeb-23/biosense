# BioSense Dataset Documentation & Provenance Standards

---

## 1. Overview & Ethical Transparency (Spec Section 29)
In computational biotechnology and academic viva evaluations, dataset provenance must be declared with complete honesty and rigorous transparency. BioSense classifies and tags every record with one of three unalterable labels:
1. `Synthetic – Demonstration Data`: Generated deterministically by mathematical models to demonstrate kinetic modeling, machine learning pipelines, and statistical routines without clinical claims.
2. `Public Dataset`: External open-access benchmarking datasets from vetted microbiological repositories.
3. `User-Uploaded`: Wet-lab spectrophotometric data or AST observations uploaded directly by authorized researchers or students.

---

## 2. Bundled Demonstration Datasets

### A. Microbial Growth Curves (`datasets/sample_growth.csv`)
- **Origin**: Generated deterministically via `scripts/generate_sample_data.py` (NumPy seed `42`).
- **Mathematical Grounding**: Verhulst Logistic Growth Equation:
  $$N(t) = \frac{K}{1 + \left(\frac{K - N_0}{N_0}\right) e^{-r t}} + \epsilon$$
  where:
  - $N_0$: Initial optical density ($0.04 \pm 0.005$)
  - $K$: Environmental carrying capacity ($1.40 \text{ to } 2.10 \text{ OD}$)
  - $r$: Specific maximum exponential growth rate ($\mu_{max}$) penalized by environmental offsets:
    $$r = r_{\text{base}} \times \max\left(0.2, 1 - \frac{|T - T_{\text{opt}}|}{25}\right) \times \max\left(0.3, 1 - \frac{|\text{pH} - \text{pH}_{\text{opt}}|}{3}\right) \times \text{Factor}_{\text{medium}}$$
  - $\epsilon$: Gaussian spectrophotometric noise $\mathcal{N}(0, 0.018)$
- **Attributes**:
  - `experiment_id`: Unique integer experiment group
  - `organism`: Scientific binary nomenclature (*Escherichia coli*, *Staphylococcus aureus*, etc.)
  - `medium`: Growth substrate (`LB Broth`, `Mueller-Hinton`, `Nutrient Agar`)
  - `temperature`: Incubation temperature in Celsius ($^\circ\text{C}$)
  - `ph`: Culture acidity/alkalinity ($0 \text{ to } 14$)
  - `time_h`: Incubation elapsed time ($0 \text{ to } 24 \text{ hours}$)
  - `optical_density`: Optical density at $600\text{ nm}$ ($\text{OD}_{600}$)
  - `data_source`: `Synthetic – Demonstration Data`

### B. Antibiotic Susceptibility Testing Records (`datasets/sample_susceptibility.csv`)
- **Origin**: Seeded synthetic distribution incorporating verified CLSI and EUCAST clinical breakpoints.
- **Microbiological Realism**:
  - **Intrinsic Resistance**: *Pseudomonas aeruginosa* against Ampicillin; Gram-negative outer membrane barrier against Glycopeptides (Vancomycin); Fungal eukaryotic wall resistance to bacterial translation inhibitors.
  - **Disk Potencies**: Standard disc potencies ($5\mu\text{g}$, $10\mu\text{g}$, $15\mu\text{g}$, $30\mu\text{g}$).
- **Categorization Rule**:
  - $\text{Zone} \ge \text{Breakpoint}_S \implies \textbf{S}$ (Susceptible)
  - $\text{Breakpoint}_R \le \text{Zone} < \text{Breakpoint}_S \implies \textbf{I}$ (Intermediate)
  - $\text{Zone} < \text{Breakpoint}_R \implies \textbf{R}$ (Resistant)
- **Attributes**:
  - `test_id`: Integer observation index
  - `organism`: Scientific species name
  - `gram_type`: `Gram-positive`, `Gram-negative`, or `Fungus`
  - `antibiotic`: Antimicrobial drug name
  - `antibiotic_class`: Pharmacological family
  - `concentration`: Disc potency in $\mu\text{g}$
  - `zone_diameter_mm`: Clear zone diameter measured across Kirby-Bauer disc in millimeters
  - `category`: `S`, `I`, or `R`
  - `data_source`: `Synthetic – Demonstration Data`

### C. Test Dirty Dataset (`datasets/sample_dirty_growth.csv`)
- Contains deliberately injected errors to validate the ingestion and data cleaning pipelines in Milestone 5:
  - Negative optical density readings ($\text{OD} = -0.15$)
  - Impossible pH values ($\text{pH} = 99.0$)
  - Sub-zero incubation temperatures ($-5^\circ\text{C}$)
  - Duplicate rows
