import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Seeded random generator for 100% deterministic reproducibility
RNG = np.random.default_rng(42)

# Reference Organism Catalog
ORGANISMS = [
    {
        "scientific_name": "Escherichia coli",
        "common_name": "E. coli",
        "genus": "Escherichia",
        "species": "coli",
        "gram_type": "Gram-negative",
        "organism_type": "bacterium",
        "domain_family": "Enterobacteriaceae",
        "opt_temp": 37.0,
        "opt_ph": 7.0,
        "max_k": 1.85,
        "base_rate": 0.55
    },
    {
        "scientific_name": "Staphylococcus aureus",
        "common_name": "S. aureus",
        "genus": "Staphylococcus",
        "species": "aureus",
        "gram_type": "Gram-positive",
        "organism_type": "bacterium",
        "domain_family": "Staphylococcaceae",
        "opt_temp": 37.0,
        "opt_ph": 7.2,
        "max_k": 1.70,
        "base_rate": 0.50
    },
    {
        "scientific_name": "Pseudomonas aeruginosa",
        "common_name": "P. aeruginosa",
        "genus": "Pseudomonas",
        "species": "aeruginosa",
        "gram_type": "Gram-negative",
        "organism_type": "bacterium",
        "domain_family": "Pseudomonadaceae",
        "opt_temp": 37.0,
        "opt_ph": 7.2,
        "max_k": 1.90,
        "base_rate": 0.48
    },
    {
        "scientific_name": "Klebsiella pneumoniae",
        "common_name": "K. pneumoniae",
        "genus": "Klebsiella",
        "species": "pneumoniae",
        "gram_type": "Gram-negative",
        "organism_type": "bacterium",
        "domain_family": "Enterobacteriaceae",
        "opt_temp": 37.0,
        "opt_ph": 7.0,
        "max_k": 1.75,
        "base_rate": 0.52
    },
    {
        "scientific_name": "Bacillus subtilis",
        "common_name": "B. subtilis",
        "genus": "Bacillus",
        "species": "subtilis",
        "gram_type": "Gram-positive",
        "organism_type": "bacterium",
        "domain_family": "Bacillaceae",
        "opt_temp": 35.0,
        "opt_ph": 7.0,
        "max_k": 1.65,
        "base_rate": 0.45
    },
    {
        "scientific_name": "Salmonella enterica",
        "common_name": "S. enterica",
        "genus": "Salmonella",
        "species": "enterica",
        "gram_type": "Gram-negative",
        "organism_type": "bacterium",
        "domain_family": "Enterobacteriaceae",
        "opt_temp": 37.0,
        "opt_ph": 7.2,
        "max_k": 1.80,
        "base_rate": 0.52
    },
    {
        "scientific_name": "Enterococcus faecalis",
        "common_name": "E. faecalis",
        "genus": "Enterococcus",
        "species": "faecalis",
        "gram_type": "Gram-positive",
        "organism_type": "bacterium",
        "domain_family": "Enterococcaceae",
        "opt_temp": 37.0,
        "opt_ph": 7.4,
        "max_k": 1.55,
        "base_rate": 0.46
    },
    {
        "scientific_name": "Streptococcus pneumoniae",
        "common_name": "S. pneumoniae",
        "genus": "Streptococcus",
        "species": "pneumoniae",
        "gram_type": "Gram-positive",
        "organism_type": "bacterium",
        "domain_family": "Streptococcaceae",
        "opt_temp": 37.0,
        "opt_ph": 7.3,
        "max_k": 1.45,
        "base_rate": 0.42
    },
    {
        "scientific_name": "Acinetobacter baumannii",
        "common_name": "A. baumannii",
        "genus": "Acinetobacter",
        "species": "baumannii",
        "gram_type": "Gram-negative",
        "organism_type": "bacterium",
        "domain_family": "Moraxellaceae",
        "opt_temp": 37.0,
        "opt_ph": 7.0,
        "max_k": 1.60,
        "base_rate": 0.44
    },
    {
        "scientific_name": "Proteus mirabilis",
        "common_name": "P. mirabilis",
        "genus": "Proteus",
        "species": "mirabilis",
        "gram_type": "Gram-negative",
        "organism_type": "bacterium",
        "domain_family": "Morganellaceae",
        "opt_temp": 37.0,
        "opt_ph": 7.2,
        "max_k": 1.70,
        "base_rate": 0.48
    },
    {
        "scientific_name": "Listeria monocytogenes",
        "common_name": "L. monocytogenes",
        "genus": "Listeria",
        "species": "monocytogenes",
        "gram_type": "Gram-positive",
        "organism_type": "bacterium",
        "domain_family": "Listeriaceae",
        "opt_temp": 35.0,
        "opt_ph": 7.0,
        "max_k": 1.40,
        "base_rate": 0.38
    },
    {
        "scientific_name": "Candida albicans",
        "common_name": "C. albicans",
        "genus": "Candida",
        "species": "albicans",
        "gram_type": "Fungus",
        "organism_type": "fungus",
        "domain_family": "Saccharomycetaceae",
        "opt_temp": 30.0,
        "opt_ph": 6.5,
        "max_k": 2.10,
        "base_rate": 0.35
    }
]

# Reference Antibiotics Catalog
ANTIBIOTICS = [
    {"name": "Ampicillin", "class": "beta-lactam", "potency": 10.0, "s_breakpoint": 17.0, "r_breakpoint": 14.0},
    {"name": "Amoxicillin", "class": "beta-lactam", "potency": 20.0, "s_breakpoint": 18.0, "r_breakpoint": 14.0},
    {"name": "Ciprofloxacin", "class": "fluoroquinolone", "potency": 5.0, "s_breakpoint": 21.0, "r_breakpoint": 16.0},
    {"name": "Gentamicin", "class": "aminoglycoside", "potency": 10.0, "s_breakpoint": 15.0, "r_breakpoint": 13.0},
    {"name": "Tetracycline", "class": "tetracycline", "potency": 30.0, "s_breakpoint": 15.0, "r_breakpoint": 12.0},
    {"name": "Vancomycin", "class": "glycopeptide", "potency": 30.0, "s_breakpoint": 17.0, "r_breakpoint": 15.0},
    {"name": "Erythromycin", "class": "macrolide", "potency": 15.0, "s_breakpoint": 23.0, "r_breakpoint": 14.0},
    {"name": "Chloramphenicol", "class": "amphenicol", "potency": 30.0, "s_breakpoint": 18.0, "r_breakpoint": 13.0},
    {"name": "Ceftriaxone", "class": "beta-lactam", "potency": 30.0, "s_breakpoint": 23.0, "r_breakpoint": 20.0},
    {"name": "Meropenem", "class": "beta-lactam", "potency": 10.0, "s_breakpoint": 22.0, "r_breakpoint": 16.0},
    {"name": "Azithromycin", "class": "macrolide", "potency": 15.0, "s_breakpoint": 18.0, "r_breakpoint": 13.0},
    {"name": "Doxycycline", "class": "tetracycline", "potency": 30.0, "s_breakpoint": 16.0, "r_breakpoint": 13.0},
    {"name": "Levofloxacin", "class": "fluoroquinolone", "potency": 5.0, "s_breakpoint": 17.0, "r_breakpoint": 14.0},
    {"name": "Amikacin", "class": "aminoglycoside", "potency": 30.0, "s_breakpoint": 17.0, "r_breakpoint": 15.0},
    {"name": "Linezolid", "class": "oxazolidinone", "potency": 30.0, "s_breakpoint": 21.0, "r_breakpoint": 21.0},
    {"name": "Clindamycin", "class": "lincosamide", "potency": 2.0, "s_breakpoint": 19.0, "r_breakpoint": 15.0}
]

MEDIA = [
    {"name": "LB Broth", "factor": 1.05},
    {"name": "Mueller-Hinton", "factor": 1.00},
    {"name": "Nutrient Agar", "factor": 0.90}
]

DATA_SOURCE_LABEL = "Synthetic – Demonstration Data"


def generate_growth_data(num_experiments: int = 150) -> pd.DataFrame:
    """Generate deterministic, noisy logistic growth curves."""
    records = []
    times = np.linspace(0, 24, 13)  # 0h to 24h every 2 hours

    for exp_id in range(1, num_experiments + 1):
        org = ORGANISMS[exp_id % len(ORGANISMS)]
        med = MEDIA[exp_id % len(MEDIA)]

        # Environmental variations around optimum
        temp = round(float(RNG.normal(org["opt_temp"], 1.5)), 1)
        ph = round(float(RNG.normal(org["opt_ph"], 0.25)), 2)

        # Kinetic parameters influenced by temperature and pH deviation
        temp_penalty = max(0.2, 1.0 - (abs(temp - org["opt_temp"]) / 25.0))
        ph_penalty = max(0.3, 1.0 - (abs(ph - org["opt_ph"]) / 3.0))
        
        r = max(0.05, org["base_rate"] * temp_penalty * ph_penalty * med["factor"])
        K = max(0.4, org["max_k"] * med["factor"] * float(RNG.normal(1.0, 0.05)))
        N0 = max(0.01, float(RNG.normal(0.04, 0.005)))

        for t in times:
            # Verhulst Logistic Model: N(t) = K / (1 + ((K - N0)/N0) * exp(-r * t))
            logistic_val = K / (1.0 + ((K - N0) / N0) * np.exp(-r * t))
            # Realistic spectrophotometric Gaussian noise
            noise = float(RNG.normal(0.0, 0.018))
            od600 = max(0.01, round(logistic_val + noise, 4))

            records.append({
                "experiment_id": exp_id,
                "organism": org["scientific_name"],
                "medium": med["name"],
                "temperature": temp,
                "ph": ph,
                "time_h": round(float(t), 1),
                "optical_density": od600,
                "data_source": DATA_SOURCE_LABEL
            })

    return pd.DataFrame(records)


def generate_susceptibility_data(num_tests: int = 1200) -> pd.DataFrame:
    """Generate deterministic antibiotic susceptibility testing records."""
    records = []

    for test_id in range(1, num_tests + 1):
        org = ORGANISMS[RNG.integers(0, len(ORGANISMS))]
        ab = ANTIBIOTICS[RNG.integers(0, len(ANTIBIOTICS))]

        # Biological intrinsic resistance rules
        # 1. P. aeruginosa is intrinsically resistant to Ampicillin
        # 2. Vancomycin is inactive against Gram-negative bacteria (membrane exclusion)
        is_intrinsic_resistant = False
        if org["scientific_name"] == "Pseudomonas aeruginosa" and ab["name"] in ["Ampicillin", "Amoxicillin"]:
            is_intrinsic_resistant = True
        elif org["gram_type"] == "Gram-negative" and ab["name"] == "Vancomycin":
            is_intrinsic_resistant = True
        elif org["gram_type"] == "Fungus":
            # Antibacterial agents are ineffective against fungal yeasts
            is_intrinsic_resistant = True

        if is_intrinsic_resistant:
            zone = float(np.clip(RNG.normal(6.0, 1.2), 0.0, 10.0))
            category = "R"
        else:
            # Stochastically distributed zone diameters
            roll = RNG.random()
            if roll < 0.65:  # Sensitive majority
                zone = float(np.clip(RNG.normal(ab["s_breakpoint"] + 4.5, 3.0), ab["s_breakpoint"], 42.0))
                category = "S"
            elif roll < 0.82:  # Intermediate
                zone = float(np.clip(RNG.normal((ab["s_breakpoint"] + ab["r_breakpoint"]) / 2.0, 1.0), ab["r_breakpoint"], ab["s_breakpoint"] - 0.1))
                category = "I"
            else:  # Acquired Resistance
                zone = float(np.clip(RNG.normal(ab["r_breakpoint"] - 4.0, 2.5), 0.0, ab["r_breakpoint"] - 0.1))
                category = "R"

        records.append({
            "test_id": test_id,
            "organism": org["scientific_name"],
            "gram_type": org["gram_type"],
            "antibiotic": ab["name"],
            "antibiotic_class": ab["class"],
            "concentration": ab["potency"],
            "zone_diameter_mm": round(zone, 1),
            "category": category,
            "data_source": DATA_SOURCE_LABEL
        })

    return pd.DataFrame(records)


def main():
    """Execute generator and write datasets to datasets/ folder."""
    out_dir = PROJECT_ROOT / "datasets"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[*] Generating synthetic biological datasets...")
    growth_df = generate_growth_data(num_experiments=150)
    sus_df = generate_susceptibility_data(num_tests=1200)

    growth_path = out_dir / "sample_growth.csv"
    sus_path = out_dir / "sample_susceptibility.csv"

    growth_df.to_csv(growth_path, index=False)
    sus_df.to_csv(sus_path, index=False)

    print(f"[+] Written {len(growth_df)} growth timepoints to: {growth_path}")
    print(f"[+] Written {len(sus_df)} AST observations to: {sus_path}")

    # Generate sample dirty dataset for ingestion validation testing (Milestone 5)
    dirty_df = growth_df.head(40).copy()
    # Inject deliberate errors: negative OD, impossible pH, and duplicates
    dirty_df.loc[0:2, "optical_density"] = -0.15
    dirty_df.loc[3:5, "ph"] = 99.0
    dirty_df.loc[6:7, "temperature"] = -5.0
    # Duplicate records
    dirty_df = pd.concat([dirty_df, dirty_df.head(4)], ignore_index=True)
    dirty_path = out_dir / "sample_dirty_growth.csv"
    dirty_df.to_csv(dirty_path, index=False)
    print(f"[+] Written {len(dirty_df)} test dirty records to: {dirty_path}")


if __name__ == "__main__":
    main()
