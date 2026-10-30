from flask import Blueprint, render_template, request, jsonify
from extensions import db, csrf
from database.models import Experiment, GrowthMeasurement, Organism, Medium
from services.growth_service import fit_logistic_growth_curve, simulate_logistic_growth

growth_bp = Blueprint("growth", __name__, url_prefix="/growth")


@growth_bp.route("/")
def index():
    """Microbial growth curve kinetics viewer and analysis engine."""
    organisms = Organism.query.order_by(Organism.scientific_name).all()
    media = Medium.query.order_by(Medium.name).all()

    # Pre-select first available organism with experiments
    selected_org_id = request.args.get("organism_id", type=int)
    if not selected_org_id and organisms:
        exp_first = Experiment.query.first()
        if exp_first:
            selected_org_id = exp_first.organism_id
        else:
            selected_org_id = organisms[0].id

    return render_template(
        "growth/growth.html",
        organisms=organisms,
        media=media,
        selected_org_id=selected_org_id
    )


@growth_bp.route("/api/curves")
def api_growth_curves():
    """Retrieve time-series measurements and fitted kinetic parameters for selected filters."""
    organism_id = request.args.get("organism_id", type=int)
    medium_id = request.args.get("medium_id", type=int)
    temp = request.args.get("temperature", type=float)

    query = Experiment.query
    if organism_id:
        query = query.filter_by(organism_id=organism_id)
    if medium_id:
        query = query.filter_by(medium_id=medium_id)
    if temp:
        query = query.filter(Experiment.temperature.between(temp - 2.0, temp + 2.0))

    experiments = query.limit(10).all()

    if not experiments:
        return jsonify({
            "success": False,
            "message": "No experimental growth curves found matching the specified filter criteria.",
            "experiments": []
        })

    results = []
    for exp in experiments:
        measurements = GrowthMeasurement.query.filter_by(experiment_id=exp.id).order_by(GrowthMeasurement.time_h).all()
        if not measurements:
            continue

        times = [m.time_h for m in measurements]
        ods = [m.optical_density for m in measurements]

        fit_data = fit_logistic_growth_curve(times, ods)
        results.append({
            "experiment_id": exp.id,
            "organism": exp.organism.scientific_name,
            "medium": exp.medium.name,
            "temperature": exp.temperature,
            "ph": exp.ph,
            "data_source": exp.data_source,
            "kinetics": fit_data
        })

    return jsonify({
        "success": True,
        "count": len(results),
        "experiments": results
    })


@growth_bp.route("/simulator")
def simulator():
    """Interactive logistic population growth simulator."""
    return render_template("growth/simulator.html")


@growth_bp.route("/api/simulate", methods=["GET", "POST"])
@csrf.exempt
def api_simulate():
    """Compute mathematical logistic growth simulation curve points."""
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form or {}
    else:
        data = request.args

    try:
        N0 = float(data.get("N0", 0.05))
        K = float(data.get("K", 1.85))
        r = float(data.get("r", 0.48))
        t_max = float(data.get("t_max", 24.0))

        sim_result = simulate_logistic_growth(N0=N0, K=K, r=r, t_max=t_max)
        return jsonify(sim_result), 200
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "notice": "Validated inputs required: N0 > 0, K > N0, r > 0, t_max > 0."
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Simulation computation failed: {str(e)}"
        }), 500
