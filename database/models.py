from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(UserMixin, db.Model):
    """User account model with Role-Based Access Control (RBAC)."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="STUDENT")  # STUDENT, RESEARCHER, ADMIN
    full_name = db.Column(db.String(120), nullable=True)
    institution = db.Column(db.String(150), nullable=True)
    research_focus = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    auth_provider = db.Column(db.String(30), default="local", nullable=False)  # local, google
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    experiments = db.relationship("Experiment", back_populates="user", cascade="all, delete-orphan")
    datasets = db.relationship("Dataset", back_populates="user", cascade="all, delete-orphan")
    ml_predictions = db.relationship("MLPrediction", back_populates="user", cascade="all, delete-orphan")
    reports = db.relationship("Report", back_populates="user", cascade="all, delete-orphan")
    audit_logs = db.relationship("AuditLog", back_populates="user")

    def set_password(self, password: str) -> None:
        """Hash and persist the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify the password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles: str) -> bool:
        """Check if user holds one of the specified roles."""
        return self.role in roles

    def __repr__(self) -> str:
        return f"<User {self.username} [{self.role}]>"


class AuditLog(db.Model):
    """System and security audit log tracking user actions."""
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} at {self.timestamp}>"


class Organism(db.Model):
    """Microbial organism reference catalog."""
    __tablename__ = "organisms"

    id = db.Column(db.Integer, primary_key=True)
    scientific_name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    common_name = db.Column(db.String(120), nullable=True)
    genus = db.Column(db.String(60), nullable=True)
    species = db.Column(db.String(60), nullable=True)
    gram_type = db.Column(db.String(30), nullable=True)  # Gram-positive, Gram-negative, Fungus
    organism_type = db.Column(db.String(50), default="bacterium")
    domain_family = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)

    experiments = db.relationship("Experiment", back_populates="organism")
    susceptibility_tests = db.relationship("SusceptibilityTest", back_populates="organism")

    def __repr__(self) -> str:
        return f"<Organism {self.scientific_name} ({self.gram_type})>"


class Antibiotic(db.Model):
    """Antimicrobial agent reference catalog."""
    __tablename__ = "antibiotics"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    antibiotic_class = db.Column(db.String(80), nullable=False)
    mechanism = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)

    susceptibility_tests = db.relationship("SusceptibilityTest", back_populates="antibiotic")

    def __repr__(self) -> str:
        return f"<Antibiotic {self.name} [{self.antibiotic_class}]>"


class Medium(db.Model):
    """Growth medium catalog for microbial cultures."""
    __tablename__ = "media"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    composition = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)

    experiments = db.relationship("Experiment", back_populates="medium")

    def __repr__(self) -> str:
        return f"<Medium {self.name}>"


class Experiment(db.Model):
    """Biological experiment linking organisms, media, environmental factors, and observations."""
    __tablename__ = "experiments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organism_id = db.Column(db.Integer, db.ForeignKey("organisms.id"), nullable=False)
    medium_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=False)
    temperature = db.Column(db.Float, nullable=False)  # in Celsius
    ph = db.Column(db.Float, nullable=False)
    incubation_time_h = db.Column(db.Float, default=24.0)
    data_source = db.Column(db.String(50), default="Synthetic – Demonstration Data", nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="experiments")
    organism = db.relationship("Organism", back_populates="experiments")
    medium = db.relationship("Medium", back_populates="experiments")
    growth_measurements = db.relationship("GrowthMeasurement", back_populates="experiment", cascade="all, delete-orphan")
    susceptibility_tests = db.relationship("SusceptibilityTest", back_populates="experiment", cascade="all, delete-orphan")
    reports = db.relationship("Report", back_populates="experiment")

    def __repr__(self) -> str:
        return f"<Experiment #{self.id} {self.organism.scientific_name if self.organism else ''}>"


class GrowthMeasurement(db.Model):
    """Time-series optical density (OD600) growth observation."""
    __tablename__ = "growth_measurements"

    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    time_h = db.Column(db.Float, nullable=False)
    optical_density = db.Column(db.Float, nullable=False)  # OD600
    growth_rate = db.Column(db.Float, nullable=True)       # Instantaneous mu

    experiment = db.relationship("Experiment", back_populates="growth_measurements")

    def __repr__(self) -> str:
        return f"<GrowthMeasurement exp={self.experiment_id} t={self.time_h}h OD={self.optical_density}>"


class SusceptibilityTest(db.Model):
    """Antibiotic Susceptibility Testing (AST) observation and S/I/R categorization."""
    __tablename__ = "susceptibility_tests"

    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=True)
    organism_id = db.Column(db.Integer, db.ForeignKey("organisms.id"), nullable=False, index=True)
    antibiotic_id = db.Column(db.Integer, db.ForeignKey("antibiotic.id" if "antibiotic" == "antibiotics" else "antibiotics.id"), nullable=False, index=True)
    concentration = db.Column(db.Float, nullable=True)      # ug/mL or disk potency
    zone_diameter_mm = db.Column(db.Float, nullable=True)   # mm
    category = db.Column(db.String(1), nullable=False)       # S, I, R
    data_source = db.Column(db.String(50), default="Synthetic – Demonstration Data", nullable=False)
    source = db.Column(db.String(30), default="recorded")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    organism = db.relationship("Organism", back_populates="susceptibility_tests")
    antibiotic = db.relationship("Antibiotic", back_populates="susceptibility_tests")
    experiment = db.relationship("Experiment", back_populates="susceptibility_tests")

    def __repr__(self) -> str:
        return f"<SusceptibilityTest {self.organism_id} x {self.antibiotic_id} -> {self.category}>"


class Dataset(db.Model):
    """Ingested dataset registry with provenance and validation status."""
    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    row_count = db.Column(db.Integer, default=0)
    rows_imported = db.Column(db.Integer, default=0)
    rows_rejected = db.Column(db.Integer, default=0)
    data_source = db.Column(db.String(50), default="User-Uploaded", nullable=False)
    status = db.Column(db.String(30), default="pending")  # pending, validated, cleaned, imported
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="datasets")

    def __repr__(self) -> str:
        return f"<Dataset {self.filename} ({self.status})>"


class MLModel(db.Model):
    """Metadata tracking trained Machine Learning models and pipelines."""
    __tablename__ = "ml_models"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    model_type = db.Column(db.String(50), nullable=False)  # classification_zone, classification_no_zone, regression
    algorithm = db.Column(db.String(80), nullable=False)   # Logistic Regression, Random Forest, Ridge, etc.
    target = db.Column(db.String(80), nullable=False)
    features_json = db.Column(db.Text, nullable=False)
    metrics_json = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    predictions = db.relationship("MLPrediction", back_populates="ml_model")

    def __repr__(self) -> str:
        return f"<MLModel {self.name} [{self.algorithm}]>"


class MLPrediction(db.Model):
    """Logged inferences and probability distributions generated by ML models."""
    __tablename__ = "ml_predictions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    model_id = db.Column(db.Integer, db.ForeignKey("ml_models.id", ondelete="SET NULL"), nullable=True)
    model_name = db.Column(db.String(120), nullable=False)
    input_json = db.Column(db.Text, nullable=False)
    prediction = db.Column(db.String(120), nullable=False)
    probability_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="ml_predictions")
    ml_model = db.relationship("MLModel", back_populates="predictions")

    def __repr__(self) -> str:
        return f"<MLPrediction {self.model_name} -> {self.prediction}>"


class Report(db.Model):
    """Generated PDF scientific reports."""
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    experiment_id = db.Column(db.Integer, db.ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="reports")
    experiment = db.relationship("Experiment", back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report {self.title}>"
