from flask import Blueprint, render_template, jsonify

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """BioSense landing page presenting core platform capabilities."""
    return render_template("index.html")


@main_bp.route("/health")
def health_check():
    """System health check endpoint for monitoring and uptime probes."""
    return jsonify({
        "status": "healthy",
        "service": "BioSense Microbial & AST Analytics Platform",
        "version": "1.0.0",
        "database": "connected"
    }), 200
