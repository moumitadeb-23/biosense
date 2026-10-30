from typing import Dict, Any, List, Optional
from sqlalchemy import func
from extensions import db
from database.models import SusceptibilityTest, Organism, Antibiotic


def get_susceptibility_summary(
    organism_id: Optional[int] = None,
    antibiotic_class: Optional[str] = None,
    data_source: Optional[str] = None
) -> Dict[str, Any]:
    """Calculate AST categorical distributions, percentages, and comparative metrics.
    
    Adheres strictly to dataset-derived phrasing rules without prescriptive advice.
    """
    query = SusceptibilityTest.query

    if organism_id:
        query = query.filter_by(organism_id=organism_id)
    if data_source:
        query = query.filter_by(data_source=data_source)
    if antibiotic_class:
        query = query.join(Antibiotic).filter(Antibiotic.antibiotic_class == antibiotic_class)

    total_tests = query.count()

    if total_tests == 0:
        return {
            "total_tests": 0,
            "counts": {"S": 0, "I": 0, "R": 0},
            "percentages": {"S": 0.0, "I": 0.0, "R": 0.0},
            "resistance_rate": 0.0,
            "observations_summary": "No antibiotic susceptibility test records found matching the specified filters.",
            "organism_breakdown": [],
            "antibiotic_breakdown": []
        }

    # Count S, I, R
    s_count = query.filter(SusceptibilityTest.category == "S").count()
    i_count = query.filter(SusceptibilityTest.category == "I").count()
    r_count = query.filter(SusceptibilityTest.category == "R").count()

    s_pct = round((s_count / total_tests) * 100.0, 1)
    i_pct = round((i_count / total_tests) * 100.0, 1)
    r_pct = round((r_count / total_tests) * 100.0, 1)

    # Organism-wise breakdown
    org_breakdown = []
    org_groups = (
        db.session.query(
            Organism.scientific_name,
            SusceptibilityTest.category,
            func.count(SusceptibilityTest.id)
        )
        .join(Organism, SusceptibilityTest.organism_id == Organism.id)
    )
    if organism_id:
        org_groups = org_groups.filter(SusceptibilityTest.organism_id == organism_id)
    if data_source:
        org_groups = org_groups.filter(SusceptibilityTest.data_source == data_source)

    org_results = org_groups.group_by(Organism.scientific_name, SusceptibilityTest.category).all()
    
    org_dict: Dict[str, Dict[str, int]] = {}
    for org_name, cat, count in org_results:
        if org_name not in org_dict:
            org_dict[org_name] = {"S": 0, "I": 0, "R": 0, "total": 0}
        org_dict[org_name][cat] = count
        org_dict[org_name]["total"] += count

    for org_name, d in org_dict.items():
        tot = max(1, d["total"])
        org_breakdown.append({
            "organism": org_name,
            "total": d["total"],
            "S": d["S"],
            "I": d["I"],
            "R": d["R"],
            "s_pct": round((d["S"] / tot) * 100.0, 1),
            "i_pct": round((d["I"] / tot) * 100.0, 1),
            "r_pct": round((d["R"] / tot) * 100.0, 1)
        })

    # Antibiotic-wise breakdown
    ab_breakdown = []
    ab_groups = (
        db.session.query(
            Antibiotic.name,
            Antibiotic.antibiotic_class,
            SusceptibilityTest.category,
            func.count(SusceptibilityTest.id),
            func.avg(SusceptibilityTest.zone_diameter_mm)
        )
        .join(Antibiotic, SusceptibilityTest.antibiotic_id == Antibiotic.id)
    )
    if organism_id:
        ab_groups = ab_groups.filter(SusceptibilityTest.organism_id == organism_id)
    if data_source:
        ab_groups = ab_groups.filter(SusceptibilityTest.data_source == data_source)

    ab_results = ab_groups.group_by(Antibiotic.name, Antibiotic.antibiotic_class, SusceptibilityTest.category).all()

    ab_dict: Dict[str, Dict[str, Any]] = {}
    for ab_name, ab_class, cat, count, avg_zone in ab_results:
        if ab_name not in ab_dict:
            ab_dict[ab_name] = {"class": ab_class, "S": 0, "I": 0, "R": 0, "total": 0, "avg_zone": 0.0}
        ab_dict[ab_name][cat] = count
        ab_dict[ab_name]["total"] += count
        if avg_zone:
            ab_dict[ab_name]["avg_zone"] = round(float(avg_zone), 1)

    for ab_name, d in ab_dict.items():
        tot = max(1, d["total"])
        ab_breakdown.append({
            "antibiotic": ab_name,
            "class": d["class"],
            "total": d["total"],
            "S": d["S"],
            "I": d["I"],
            "R": d["R"],
            "s_pct": round((d["S"] / tot) * 100.0, 1),
            "i_pct": round((d["I"] / tot) * 100.0, 1),
            "r_pct": round((d["R"] / tot) * 100.0, 1),
            "avg_zone": d["avg_zone"]
        })

    # Sort antibiotics by Sensitive percentage descending
    ab_breakdown.sort(key=lambda x: x["s_pct"], reverse=True)

    # Dataset-derived phrasing generation
    observations_text = ""
    if ab_breakdown:
        top_sensitive_ab = ab_breakdown[0]
        org_label = "the filtered species"
        if organism_id:
            selected_org = Organism.query.get(organism_id)
            if selected_org:
                org_label = selected_org.scientific_name

        observations_text = (
            f"Within the analyzed dataset ({total_tests} observations), {top_sensitive_ab['antibiotic']} "
            f"({top_sensitive_ab['class']}) had the highest proportion of observations categorized as Sensitive "
            f"({top_sensitive_ab['s_pct']}%) for {org_label}. Overall resistance frequency within this sample was {r_pct}%."
        )

    return {
        "total_tests": total_tests,
        "counts": {"S": s_count, "I": i_count, "R": r_count},
        "percentages": {"S": s_pct, "I": i_pct, "R": r_pct},
        "resistance_rate": r_pct,
        "observations_summary": observations_text,
        "organism_breakdown": org_breakdown,
        "antibiotic_breakdown": ab_breakdown
    }
