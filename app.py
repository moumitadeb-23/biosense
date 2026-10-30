import os
from datetime import datetime
from flask import Flask, render_template
from config import config_by_name, Config
from extensions import db, login_manager, csrf


def create_app(config_name=None, config_override=None):
    """Application factory for BioSense platform."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, Config))

    if config_override:
        app.config.update(config_override)

    # Ensure critical filesystem directories exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["MODEL_FOLDER"], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Configure user session loader
    @login_manager.user_loader
    def load_user(user_id):
        from database.models import User
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # Context processor for global template variables
    @app.context_processor
    def inject_global_template_vars():
        return {
            "current_year": datetime.utcnow().year,
            "clinical_disclaimer": "Educational/Research Analytics — Not for Clinical Diagnosis or Treatment Decisions.",
            "platform_name": "BioSense",
            "tagline": "Turning Biological Data into Intelligent Insights."
        }

    # Template filters
    @app.template_filter("from_json")
    def from_json_filter(val):
        if not val:
            return {}
        if isinstance(val, dict):
            return val
        try:
            import json
            return json.loads(val)
        except Exception:
            return {}

    # Register blueprints
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.datasets import datasets_bp
    from routes.growth import growth_bp
    from routes.susceptibility import susceptibility_bp
    from routes.statistics import statistics_bp
    from routes.ml import ml_bp
    from routes.reports import reports_bp
    from routes.admin import admin_bp
    from routes.learn import learn_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(datasets_bp)
    app.register_blueprint(growth_bp)
    app.register_blueprint(susceptibility_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(ml_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(learn_bp)

    # Friendly error handling without leaking stack traces in production
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    # Auto-create tables for development/SQLite convenience
    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app("development")
    app.run(host="127.0.0.1", port=5000, debug=True)
