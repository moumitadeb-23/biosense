from flask import Blueprint, render_template, request, jsonify, abort
from extensions import db
from database.models import Organism, Medium, Experiment, GrowthMeasurement, SusceptibilityTest
from services.statistics_service import (
    compute_descriptive_statistics,
    run_welch_ttest,
    run_one_way_anova,
    get_organism_bio_explorer_profile,
)

statistics_bp = Blueprint("statistics", __name__, url_prefix="/statistics")


@statistics_bp.route("/")
def index():
    """Descriptive statistics, correlation matrix, and inferential hypothesis testing suite."""
    stats_data = compute_descriptive_statistics()
    media = Medium.query.order_by(Medium.name).all()
    organisms = Organism.query.order_by(Organism.scientific_name).all()

    return render_template(
        "statistics/statistics.html",
        stats_data=stats_data,
        media=media,
        organisms=organisms
    )


@statistics_bp.route("/api/summary")
def api_summary():
    """JSON API returning continuous variable metrics and Pearson correlation matrix."""
    return jsonify(compute_descriptive_statistics())


@statistics_bp.route("/api/hypothesis-test", methods=["POST"])
def api_hypothesis_test():
    """Run Welch's t-test or One-Way ANOVA dynamically on database observations."""
    payload = request.get_json() or {}
    test_type = payload.get("test_type", "ttest")  # 'ttest' or 'anova'

    if test_type == "ttest":
        # Example 1: Compare Peak OD of Gram-positive vs Gram-negative bacteria
        # or compare culture temperature subgroups (< 35 vs >= 35)
        group_col = payload.get("group_col", "gram_type")
        metric_col = payload.get("metric_col", "optical_density")

        if group_col == "gram_type":
            gp_query = (
                db.session.query(GrowthMeasurement.optical_density)
                .join(Experiment, GrowthMeasurement.experiment_id == Experiment.id)
                .join(Organism, Experiment.organism_id == Organism.id)
                .filter(Organism.gram_type == "Gram-positive")
                .all()
            )
            gn_query = (
                db.session.query(GrowthMeasurement.optical_density)
                .join(Experiment, GrowthMeasurement.experiment_id == Experiment.id)
                .join(Organism, Experiment.organism_id == Organism.id)
                .filter(Organism.gram_type == "Gram-negative")
                .all()
            )
            vals_a = [r[0] for r in gp_query if r[0] is not None]
            vals_b = [r[0] for r in gn_query if r[0] is not None]
            result = run_welch_ttest(vals_a, vals_b, label_a="Gram-positive Bacteria", label_b="Gram-negative Bacteria")
            return jsonify(result)

        else:
            # Default temperature median split comparison
            median_temp = 36.0
            t_low = (
                db.session.query(GrowthMeasurement.optical_density)
                .join(Experiment, GrowthMeasurement.experiment_id == Experiment.id)
                .filter(Experiment.temperature < median_temp)
                .all()
            )
            t_high = (
                db.session.query(GrowthMeasurement.optical_density)
                .join(Experiment, GrowthMeasurement.experiment_id == Experiment.id)
                .filter(Experiment.temperature >= median_temp)
                .all()
            )
            result = run_welch_ttest(
                [r[0] for r in t_low if r[0] is not None],
                [r[0] for r in t_high if r[0] is not None],
                label_a=f"Sub-optimal Temp (< {median_temp}°C)",
                label_b=f"Standard/Elevated Temp (≥ {median_temp}°C)"
            )
            return jsonify(result)

    elif test_type == "anova":
        # Compare Optical Density across different culture media (LB Broth, Mueller-Hinton, Nutrient Agar)
        media_list = Medium.query.all()
        groups_dict = {}
        for med in media_list:
            od_rows = (
                db.session.query(GrowthMeasurement.optical_density)
                .join(Experiment, GrowthMeasurement.experiment_id == Experiment.id)
                .filter(Experiment.medium_id == med.id)
                .all()
            )
            groups_dict[med.name] = [r[0] for r in od_rows if r[0] is not None]

        result = run_one_way_anova(groups_dict)
        return jsonify(result)

    return jsonify({"success": False, "error": "Unknown test type"}), 400


@statistics_bp.route("/explorer")
def bio_explorer():
    """Bio Explorer microbial encyclopedia and searchable organism directory."""
    search_query = request.args.get("q", "").strip()
    gram_filter = request.args.get("gram", "").strip()

    query = Organism.query
    if search_query:
        query = query.filter(
            (Organism.scientific_name.ilike(f"%{search_query}%")) |
            (Organism.common_name.ilike(f"%{search_query}%")) |
            (Organism.genus.ilike(f"%{search_query}%")) |
            (Organism.domain_family.ilike(f"%{search_query}%"))
        )
    if gram_filter:
        query = query.filter_by(gram_type=gram_filter)

    organisms = query.order_by(Organism.scientific_name).all()

    # Pre-calculate counts for each organism
    profiles = []
    for org in organisms:
        exp_c = Experiment.query.filter_by(organism_id=org.id).count()
        ast_c = SusceptibilityTest.query.filter_by(organism_id=org.id).count()
        profiles.append({
            "organism": org,
            "experiment_count": exp_c,
            "ast_count": ast_c
        })

    return render_template(
        "statistics/bio_explorer.html",
        profiles=profiles,
        search_query=search_query,
        gram_filter=gram_filter
    )


@statistics_bp.route("/explorer/<int:organism_id>")
def organism_detail(organism_id: int):
    """Detailed biological and observational profile page for an organism."""
    profile = get_organism_bio_explorer_profile(organism_id)
    if not profile:
        abort(404)

    return render_template("statistics/organism_profile.html", profile=profile)
