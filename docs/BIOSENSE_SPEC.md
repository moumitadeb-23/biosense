# BioSense: Master Specification & Platform Architecture
**Intelligent Microbial Growth & Antibiotic Susceptibility Analytics Platform**
*Tagline: "Turning Biological Data into Intelligent Insights."*

---

## 1. Executive Summary & Vision
BioSense is a production-grade full-stack biotech analytics platform designed for researchers, educators, and students in data science and computational biology. It combines microbial growth kinetics modeling, clinical-standard antibiotic susceptibility testing (AST) analysis, dynamic machine learning pipelines, anomaly screening, and automated PDF report generation into a unified, secure web platform.

---

## 2. Target Audience & Educational Mission
Targeted primarily for academic viva defense, data science research, and educational laboratory analysis:
- **Student Persona**: Uploads growth or susceptibility data, visualizes lag/log/stationary phases, tests logistic growth simulations, and trains classification/regression models.
- **Researcher Persona**: Compares antibiotic efficacy profiles across multiple bacterial strains, calculates specific growth rates ($\mu_{max}$), doubling times, and generates comprehensive PDF reports.
- **Admin Persona**: Governs reference organism and antibiotic catalogs, monitors audit logs, and oversees data integrity.

---

## 3. Technology Stack & Architectural Standards
- **Backend**: Python 3.10+, Flask with Blueprints and Application Factory (`create_app`) pattern.
- **ORM & Database**: Flask-SQLAlchemy with SQLite (local development) and portable dialect support for PostgreSQL/MySQL via `DATABASE_URL`.
- **Security & Authentication**: Flask-Login session management, Flask-WTF CSRF protection, Werkzeug password hashing (scrypt/pbkdf2), role-based access control (RBAC).
- **Data Science & ML**: NumPy, Pandas, SciPy (curve fitting, stats), Scikit-Learn (pipelines, classification, regression, anomaly detection, permutation importance).
- **Visualization**: Plotly.js (interactive client-side charts via CDN), Matplotlib (headless Agg backend for high-res PDF graphics).
- **Reporting**: ReportLab 3.x / 4.x / 5.x for publication-quality PDF document creation.
- **Testing & Tooling**: Pytest, python-dotenv, Gunicorn (production WSGI).

---

## 4. Scientific Rigor & Compliance Standards (Section 29)
1. **Educational & Research Notice**: Explicitly displayed on the landing page, dashboard, susceptibility views, ML lab, and embedded on every generated PDF footer:
   > *"Educational/Research Analytics — Not for Clinical Diagnosis or Treatment Decisions."*
2. **Dataset-Derived Language**: Susceptibility conclusions are phrased as:
   > *"Within the analyzed dataset, Antibiotic X had the highest proportion of observations categorized as Sensitive for Organism Y."*
   Prescriptive phrases such as "prescribe", "drug of choice", or "treatment recommendation" are strictly forbidden.
3. **Data Provenance**: Every record is tagged with its provenance:
   - `Synthetic – Demonstration Data`
   - `Public Dataset`
   - `User-Uploaded`

---

## 5. Architectural Directory Layout (Section 24)
```text
biosense/
├── app.py                      # Application runner / WSGI entry point
├── config.py                   # Environment-driven configuration classes
├── extensions.py               # Instantiation of db, login_manager, csrf
├── requirements.txt            # Pinned production dependencies
├── Procfile                    # Render / Heroku WSGI command
├── render.yaml                 # Render deployment configuration
├── .env.example                # Template for environment variables
├── .gitignore                  # Git hygiene rules
├── README.md                   # Complete setup, viva defense, & user manual
├── PROGRESS.md                 # Real-time milestone progress log
├── database/
│   ├── __init__.py
│   └── models.py               # SQLAlchemy ORM models & relationships
├── datasets/
│   ├── sample_growth.csv       # Seeded synthetic growth curves
│   └── sample_susceptibility.csv # Seeded synthetic AST data
├── models/                     # Saved joblib/pickle ML pipeline artifacts
├── routes/                     # Blueprint controllers (thin routes)
│   ├── __init__.py
│   ├── auth.py                 # Registration, login, logout, profile
│   ├── main.py                 # Landing page & health check
│   ├── dashboard.py            # KPI aggregation & visualization endpoints
│   ├── datasets.py             # CSV upload, validation, cleaning, import
│   ├── growth.py               # Growth curves, phase analysis, simulation
│   ├── susceptibility.py       # AST breakdown, resistance trends
│   ├── statistics.py           # Descriptive stats, t-test, ANOVA, Bio Explorer
│   ├── ml.py                   # Model training, comparison, prediction, explainability
│   ├── reports.py              # PDF generator and download manager
│   └── admin.py                # Reference catalog editor & audit viewer
├── services/                   # Core business logic & scientific algorithms
│   ├── __init__.py
│   ├── auth_service.py         # User & audit log management
│   ├── validation_service.py   # Ingestion rules & schema checks
│   ├── cleaning_service.py     # Missing value, duplicate, formula protection
│   ├── growth_service.py       # Curve fitting, $\mu_{max}$, doubling time
│   ├── susceptibility_service.py # AST categorization, resistance statistics
│   ├── statistics_service.py   # Statistical tests, correlations, summaries
│   ├── ml_service.py           # Sklearn pipelines, classification, regression, explainability
│   ├── anomaly_service.py      # IQR, Z-score, Isolation Forest
│   └── report_service.py       # 13-section ReportLab PDF builder
├── templates/                  # Jinja2 templates (semantic HTML5, Bootstrap 5)
│   ├── base.html               # Master layout with navbar, theme toggle, footer
│   ├── index.html              # Biotech SaaS landing page
│   ├── auth/                   # login.html, register.html, profile.html
│   ├── dashboard/              # dashboard.html
│   ├── datasets/               # upload.html, preview.html, validate.html
│   ├── growth/                 # growth.html, simulator.html
│   ├── susceptibility/         # susceptibility.html
│   ├── statistics/             # statistics.html, bio_explorer.html
│   ├── ml/                     # classification.html, regression.html, compare.html, explain.html, anomaly.html
│   ├── reports/                # reports.html, view_report.html
│   ├── admin/                  # admin.html, audit_logs.html
│   └── errors/                 # 403.html, 404.html, 500.html
├── static/
│   ├── css/
│   │   └── biosense.css        # Custom biotechnological theme & dark/light styles
│   ├── js/
│   │   ├── main.js             # Theme toggle & UI interactions
│   │   ├── dashboard.js        # Plotly charts integration
│   │   └── ml_charts.js        # ROC, Confusion Matrix, Actual vs Predicted
│   └── images/
├── tests/                      # Comprehensive Pytest suite
│   ├── conftest.py             # Pytest fixtures & test database setup
│   ├── test_auth.py            # RBAC, login, registration, security tests
│   ├── test_dataset.py         # Upload, validation, cleaning checks
│   ├── test_growth.py          # Mathematical formula & curve fit tests
│   ├── test_susceptibility.py  # AST categorization tests
│   ├── test_statistics.py      # Welch t-test & ANOVA tests
│   ├── test_ml.py              # ML pipelines, classification & regression tests
│   ├── test_anomaly.py         # Isolation Forest & Z-score tests
│   └── test_reports.py         # PDF generation tests
├── scripts/
│   ├── create_admin.py         # CLI for initial administrator bootstrap
│   └── generate_sample_data.py # Seeded synthetic data generator
└── docs/
    ├── BIOSENSE_SPEC.md        # This master specification
    ├── ARCHITECTURE.md         # Full system architecture & Mermaid diagrams
    ├── DATABASE_SCHEMA.md      # Relational schema & entity definitions
    ├── ML_METHODOLOGY.md       # Preprocessing, algorithms, metrics & caveats
    ├── DATASETS.md             # Dataset documentation & provenance
    ├── LEARNING_NOTES.md       # Beginner explanations for 4th-year BCA defense
    └── VIVA_QA.md              # 30+ detailed viva questions with answers
```

---

## 6. Milestone Plan (M1–M14)
1. **M1: Foundation**: Virtual environment instructions, `config.py`, `.env.example`, `.gitignore`, app factory (`app.py`), base layout, health check route, first pytest.
2. **M2: Landing Page**: High-end Biotech SaaS presentation, hero, workflow, feature matrix, tech stack, statistics showcase, DNA/scientific grid styling, responsive dark/light theme switch.
3. **M3: Database & Auth**: SQLAlchemy schema, roles (STUDENT, RESEARCHER, ADMIN), session management, password hashing, audit logs, CLI admin creator.
4. **M4: Reference Data & Seed Generators**: Standard microbiology catalogs (organisms, antibiotics, media), deterministic noisy logistic growth data & synthetic AST records.
5. **M5: Dataset Management**: CSV upload, schema verification, range validation, formula-injection protection, data cleaning pipeline, confirmation & database import.
6. **M6: Growth Analysis & Simulation**: Time-OD curve plotting, exponential slope growth rate ($\mu_{max}$), doubling time ($t_d$), phase segmentation heuristics, interactive logistic simulator.
7. **M7: Susceptibility Analytics**: S/I/R categorization, distribution metrics, comparative bar/donut charts, non-prescriptive biological summaries.
8. **M8: Statistics & Bio Explorer**: Descriptive stats, correlation heatmap, Welch's t-test, one-way ANOVA, organism-centric Bio Explorer directory.
9. **M9: Dashboard**: 6 KPI summary cards, 8 Plotly charts, dynamic audit feed, empty-state fallback with sample seeding button.
10. **M10: Machine Learning Lab**: Dual classification pipelines (with/without zone diameter), regression pipelines for OD prediction, model comparisons, explainability (permutation importance), and anomaly detection.
11. **M11: PDF Report Generator**: 13-section ReportLab engine with embedded charts, tables, statistical findings, ML insights, and clinical disclaimers.
12. **M12: Polish & Accessibility**: Light/Dark contrast compliance, responsive layouts, friendly error handlers (403, 404, 500), empty states.
13. **M13: Testing**: Complete pytest suite across all subsystems, ensuring zero failures.
14. **M14: Documentation & Deployment**: Comprehensive README, viva Q&A, deployment manifests (Procfile, render.yaml), and viva defense preparation notes.
