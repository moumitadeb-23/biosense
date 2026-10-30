from flask import Blueprint, render_template, jsonify, flash, redirect, url_for, request
from sqlalchemy import func, case
from extensions import db
from database.models import (
    Experiment,
    GrowthMeasurement,
    SusceptibilityTest,
    Organism,
    Antibiotic,
    Medium,
    AuditLog,
)
from services.auth_service import log_audit
from scripts.seed_db import seed_database

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
def index():
    """Main executive analytics dashboard with 6 KPIs and 8 interactive visualizations."""
    exp_count = Experiment.query.count()
    org_count = Organism.query.count()
    ab_count = Antibiotic.query.count()
    growth_count = GrowthMeasurement.query.count()
    ast_count = SusceptibilityTest.query.count()

    # Calculate overall resistance rate
    r_count = SusceptibilityTest.query.filter_by(category="R").count()
    resistance_rate = round((r_count / max(1, ast_count)) * 100.0, 1) if ast_count > 0 else 0.0

    is_empty_state = (exp_count == 0 and ast_count == 0)

    # Recent Audit Log Activity
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(8).all()

    return render_template(
        "dashboard/dashboard.html",
        exp_count=exp_count,
        org_count=org_count,
        ab_count=ab_count,
        growth_count=growth_count,
        ast_count=ast_count,
        resistance_rate=resistance_rate,
        is_empty_state=is_empty_state,
        recent_logs=recent_logs
    )


@dashboard_bp.route("/api/charts")
def api_charts():
    """Aggregate real database records into payload structures for 8 Plotly charts."""
    # 1. Growth Trajectories: Sample 5 distinct organisms
    top_exps = (
        db.session.query(Experiment.id, Organism.scientific_name)
        .join(Organism, Experiment.organism_id == Organism.id)
        .limit(5)
        .all()
    )
    growth_trajectories = []
    for exp_id, org_name in top_exps:
        measurements = (
            GrowthMeasurement.query.filter_by(experiment_id=exp_id)
            .order_by(GrowthMeasurement.time_h)
            .all()
        )
        if measurements:
            growth_trajectories.append({
                "organism": org_name,
                "x": [m.time_h for m in measurements],
                "y": [round(m.optical_density, 3) for m in measurements]
            })

    # 2. Susceptibility Donut (S, I, R)
    s_count = SusceptibilityTest.query.filter_by(category="S").count()
    i_count = SusceptibilityTest.query.filter_by(category="I").count()
    r_count = SusceptibilityTest.query.filter_by(category="R").count()
    ast_donut = {
        "labels": ["Sensitive (S)", "Intermediate (I)", "Resistant (R)"],
        "values": [s_count, i_count, r_count],
        "colors": ["#10b981", "#f59e0b", "#f43f5e"]
    }

    # 3. Temperature vs Optical Density Scatter (sample 150 points)
    temp_od_query = (
        db.session.query(Experiment.temperature, GrowthMeasurement.optical_density, Organism.scientific_name)
        .join(Experiment, GrowthMeasurement.experiment_id == Experiment.id)
        .join(Organism, Experiment.organism_id == Organism.id)
        .limit(200)
        .all()
    )
    temp_od_scatter = {
        "temp": [round(r[0], 1) for r in temp_od_query if r[0] is not None and r[1] is not None],
        "od": [round(r[1], 3) for r in temp_od_query if r[0] is not None and r[1] is not None],
        "text": [r[2] for r in temp_od_query if r[0] is not None and r[1] is not None]
    }

    # 4. Antibiotic Resistance Rates across top 8 tested agents
    r_case = case([(SusceptibilityTest.category == "R", 1)], else_=0)
    ab_res_query = (
        db.session.query(
            Antibiotic.name,
            func.count(SusceptibilityTest.id),
            func.sum(r_case)
        )
        .join(Antibiotic, SusceptibilityTest.antibiotic_id == Antibiotic.id)
        .group_by(Antibiotic.name)
        .order_by(func.count(SusceptibilityTest.id).desc())
        .limit(8)
        .all()
    )
    ab_resistance = {
        "antibiotics": [r[0] for r in ab_res_query],
        "resistance_rates": [round((float(r[2]) / max(1, r[1])) * 100.0, 1) if r[2] is not None else 0.0 for r in ab_res_query]
    }

    # 5. Culture pH Distribution Histogram
    ph_query = db.session.query(Experiment.ph).filter(Experiment.ph.isnot(None)).limit(300).all()
    ph_dist = [round(r[0], 2) for r in ph_query if r[0] is not None]

    # 6. Media Yield Comparison (Mean OD across media)
    media_yield_query = (
        db.session.query(
            Medium.name,
            func.avg(GrowthMeasurement.optical_density),
            func.count(GrowthMeasurement.id)
        )
        .join(Experiment, GrowthMeasurement.experiment_id == Experiment.id)
        .join(Medium, Experiment.medium_id == Medium.id)
        .group_by(Medium.name)
        .all()
    )
    media_yield = {
        "media": [r[0] for r in media_yield_query],
        "avg_od": [round(float(r[1]), 3) if r[1] is not None else 0.0 for r in media_yield_query]
    }

    # 7. Gram Positive vs Gram Negative Susceptibility Comparison
    gram_ast_query = (
        db.session.query(
            Organism.gram_type,
            SusceptibilityTest.category,
            func.count(SusceptibilityTest.id)
        )
        .join(Organism, SusceptibilityTest.organism_id == Organism.id)
        .filter(Organism.gram_type.in_(["Gram-positive", "Gram-negative"]))
        .group_by(Organism.gram_type, SusceptibilityTest.category)
        .all()
    )
    gram_dict = {"Gram-positive": {"S": 0, "R": 0}, "Gram-negative": {"S": 0, "R": 0}}
    for gram, cat, c in gram_ast_query:
        if cat in ["S", "R"]:
            gram_dict[gram][cat] += c

    gram_comparison = {
        "categories": ["Gram-positive", "Gram-negative"],
        "sensitive": [gram_dict["Gram-positive"]["S"], gram_dict["Gram-negative"]["S"]],
        "resistant": [gram_dict["Gram-positive"]["R"], gram_dict["Gram-negative"]["R"]]
    }

    # 8. Activity Volume Timeline: Experiments per incubation time
    time_points_query = (
        db.session.query(
            GrowthMeasurement.time_h,
            func.count(GrowthMeasurement.id)
        )
        .group_by(GrowthMeasurement.time_h)
        .order_by(GrowthMeasurement.time_h)
        .all()
    )
    timeline = {
        "hours": [round(r[0], 1) for r in time_points_query],
        "counts": [r[1] for r in time_points_query]
    }

    return jsonify({
        "growth_trajectories": growth_trajectories,
        "ast_donut": ast_donut,
        "temp_od_scatter": temp_od_scatter,
        "ab_resistance": ab_resistance,
        "ph_dist": ph_dist,
        "media_yield": media_yield,
        "gram_comparison": gram_comparison,
        "timeline": timeline
    })


@dashboard_bp.route("/api/seed-demo", methods=["POST"])
def api_seed_demo():
    """One-click sample data seeding handler for empty database state."""
    try:
        from scripts.generate_sample_data import main as gen_main
        gen_main()
        seed_database(load_samples=True)
        log_audit(action="DEMO_DATA_SEEDED", details="Seeded demonstration data from dashboard banner")
        flash("Demonstration dataset successfully loaded! Analytics visualizations are now live.", "success")
        return jsonify({"success": True, "message": "Demo data populated."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
