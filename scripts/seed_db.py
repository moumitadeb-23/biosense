import sys
import os
from pathlib import Path
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from extensions import db
from database.models import (
    User,
    AuditLog,
    Organism,
    Antibiotic,
    Medium,
    Experiment,
    GrowthMeasurement,
    SusceptibilityTest,
)
from scripts.generate_sample_data import ORGANISMS, ANTIBIOTICS, MEDIA


def seed_database(app=None, load_samples=True):
    """Seed reference biological catalogs, default demo users, and sample experimental records."""
    if app is None:
        from flask import current_app
        try:
            if current_app:
                app = current_app._get_current_object()
        except Exception:
            app = None

    if app is None:
        app = create_app()

    with app.app_context():
        print("[*] Initializing database tables...")
        db.create_all()

        # 1. Seed Demo Accounts
        demo_users = [
            ("admin", "admin@biosense.local", "ADMIN", "BioSense123!"),
            ("researcher", "researcher@biosense.local", "RESEARCHER", "BioSense123!"),
            ("student", "student@biosense.local", "STUDENT", "BioSense123!")
        ]
        created_users = {}
        for username, email, role, password in demo_users:
            u = User.query.filter_by(username=username).first()
            if not u:
                u = User(username=username, email=email, role=role)
                u.set_password(password)
                db.session.add(u)
                db.session.flush()
                print(f"[+] Created user: {username} [{role}]")
            created_users[role] = u

        # 2. Seed Reference Organisms
        organism_map = {}
        for org_data in ORGANISMS:
            org = Organism.query.filter_by(scientific_name=org_data["scientific_name"]).first()
            if not org:
                desc = (
                    f"{org_data['scientific_name']} is a {org_data['gram_type'].lower()} {org_data['organism_type']} "
                    f"belonging to family {org_data['domain_family']}. Standard laboratory model with optimal "
                    f"growth near {org_data['opt_temp']}°C and pH {org_data['opt_ph']}."
                )
                org = Organism(
                    scientific_name=org_data["scientific_name"],
                    common_name=org_data["common_name"],
                    genus=org_data["genus"],
                    species=org_data["species"],
                    gram_type=org_data["gram_type"],
                    organism_type=org_data["organism_type"],
                    domain_family=org_data["domain_family"],
                    description=desc
                )
                db.session.add(org)
                db.session.flush()
            organism_map[org_data["scientific_name"]] = org

        # 3. Seed Reference Antibiotics
        antibiotic_map = {}
        mechanisms = {
            "beta-lactam": "Inhibition of bacterial cell wall peptidoglycan synthesis via PBP binding.",
            "fluoroquinolone": "Inhibition of bacterial DNA gyrase (topoisomerase II) and topoisomerase IV.",
            "aminoglycoside": "Binds irreversible to 30S ribosomal subunit, causing mRNA mistranslation.",
            "tetracycline": "Reversibly binds 30S ribosomal subunit, blocking aminoacyl-tRNA attachment.",
            "glycopeptide": "Binds D-alanyl-D-alanine termini, preventing cell wall cross-linking.",
            "macrolide": "Binds 50S ribosomal subunit, inhibiting peptide translocation.",
            "amphenicol": "Binds 50S ribosomal subunit, inhibiting peptidyl transferase activity.",
            "oxazolidinone": "Binds 50S subunit at 23S rRNA, preventing 70S initiation complex formation.",
            "lincosamide": "Binds 50S ribosomal subunit, suppressing transpeptidation."
        }
        for ab_data in ANTIBIOTICS:
            ab = Antibiotic.query.filter_by(name=ab_data["name"]).first()
            if not ab:
                ab = Antibiotic(
                    name=ab_data["name"],
                    antibiotic_class=ab_data["class"],
                    mechanism=mechanisms.get(ab_data["class"], "Antimicrobial mechanism of action."),
                    description=f"{ab_data['name']} is a standard clinical {ab_data['class']} antimicrobial agent."
                )
                db.session.add(ab)
                db.session.flush()
            antibiotic_map[ab_data["name"]] = ab

        # 4. Seed Reference Media
        media_map = {}
        media_descriptions = {
            "LB Broth": "Nutritionally rich liquid lysogeny broth optimized for molecular biology and enteric cultures.",
            "Mueller-Hinton": "Designated CLSI and EUCAST standard agar medium for Kirby-Bauer antimicrobial disk diffusion.",
            "Nutrient Agar": "General purpose non-fastidious cultivation medium containing beef extract and peptone."
        }
        for med_data in MEDIA:
            med = Medium.query.filter_by(name=med_data["name"]).first()
            if not med:
                med = Medium(
                    name=med_data["name"],
                    composition="Enzymatic digest, mineral salts, and organic buffers.",
                    description=media_descriptions.get(med_data["name"], "Microbial growth culture medium.")
                )
                db.session.add(med)
                db.session.flush()
            media_map[med_data["name"]] = med

        db.session.commit()
        print(f"[+] Reference catalogs seeded ({len(organism_map)} organisms, {len(antibiotic_map)} antibiotics, {len(media_map)} media).")

        # 5. Optionally Ingest Seeded Sample Data
        if load_samples:
            growth_csv = PROJECT_ROOT / "datasets" / "sample_growth.csv"
            sus_csv = PROJECT_ROOT / "datasets" / "sample_susceptibility.csv"

            if growth_csv.exists() and Experiment.query.count() == 0:
                print("[*] Ingesting sample growth experiments into database...")
                gdf = pd.read_csv(growth_csv)
                admin_user = created_users["ADMIN"]

                # Group by experiment
                grouped = gdf.groupby(["experiment_id", "organism", "medium", "temperature", "ph"])
                for (exp_id, org_name, med_name, temp, ph), grp in grouped:
                    exp = Experiment(
                        user_id=admin_user.id,
                        organism_id=organism_map[org_name].id,
                        medium_id=media_map[med_name].id,
                        temperature=float(temp),
                        ph=float(ph),
                        incubation_time_h=float(grp["time_h"].max()),
                        data_source="Synthetic – Demonstration Data",
                        notes=f"Automated benchmark experiment #{exp_id} under {temp}°C and pH {ph}."
                    )
                    db.session.add(exp)
                    db.session.flush()

                    for _, row in grp.iterrows():
                        m = GrowthMeasurement(
                            experiment_id=exp.id,
                            time_h=float(row["time_h"]),
                            optical_density=float(row["optical_density"]),
                            growth_rate=0.45
                        )
                        db.session.add(m)

                db.session.commit()
                print(f"[+] Loaded {Experiment.query.count()} experiments with {GrowthMeasurement.query.count()} growth measurements.")

            if sus_csv.exists() and SusceptibilityTest.query.count() == 0:
                print("[*] Ingesting sample susceptibility records into database...")
                sdf = pd.read_csv(sus_csv)

                for _, row in sdf.iterrows():
                    test = SusceptibilityTest(
                        organism_id=organism_map[row["organism"]].id,
                        antibiotic_id=antibiotic_map[row["antibiotic"]].id,
                        concentration=float(row["concentration"]),
                        zone_diameter_mm=float(row["zone_diameter_mm"]),
                        category=str(row["category"]),
                        data_source="Synthetic – Demonstration Data",
                        source="synthetic"
                    )
                    db.session.add(test)

                db.session.commit()
                print(f"[+] Loaded {SusceptibilityTest.query.count()} AST susceptibility test records.")

        # Record audit log
        log = AuditLog(
            user_id=created_users["ADMIN"].id if "ADMIN" in created_users else None,
            action="DATABASE_SEEDED",
            details="Database populated with reference organisms, antibiotics, and demo datasets",
            ip_address="127.0.0.1"
        )
        db.session.add(log)
        db.session.commit()
        print("[SUCCESS] Database seeding complete!")


if __name__ == "__main__":
    seed_database()
