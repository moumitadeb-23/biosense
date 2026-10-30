from flask import Blueprint, render_template, request, jsonify
from extensions import db
from database.models import SusceptibilityTest, Organism, Antibiotic
from services.susceptibility_service import get_susceptibility_summary

susceptibility_bp = Blueprint("susceptibility", __name__, url_prefix="/susceptibility")


@susceptibility_bp.route("/")
def index():
    """Antibiotic Susceptibility Testing (AST) analytics overview."""
    organisms = Organism.query.order_by(Organism.scientific_name).all()
    antibiotic_classes = (
        db.session.query(Antibiotic.antibiotic_class)
        .distinct()
        .order_by(Antibiotic.antibiotic_class)
        .all()
    )
    ab_classes = [c[0] for c in antibiotic_classes if c[0]]

    # Initial summary
    initial_summary = get_susceptibility_summary()

    return render_template(
        "susceptibility/susceptibility.html",
        organisms=organisms,
        antibiotic_classes=ab_classes,
        summary=initial_summary
    )


@susceptibility_bp.route("/api/summary")
def api_summary():
    """JSON API returning filtered AST categorical distributions and efficacy tables."""
    organism_id = request.args.get("organism_id", type=int)
    antibiotic_class = request.args.get("antibiotic_class", type=str)
    data_source = request.args.get("data_source", type=str)

    if antibiotic_class == "":
        antibiotic_class = None
    if data_source == "":
        data_source = None

    summary = get_susceptibility_summary(
        organism_id=organism_id,
        antibiotic_class=antibiotic_class,
        data_source=data_source
    )

    return jsonify(summary)
