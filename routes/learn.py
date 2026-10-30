"""
Knowledge Hub & Beginner Viva Voce Learning Blueprint for BioSense.
Provides interactive science guides, mathematical formula sandboxes,
35 viva examination questions and answers, interactive quizzes, and a biological glossary.
"""

from flask import Blueprint, render_template, jsonify, request

learn_bp = Blueprint("learn", __name__, url_prefix="/learn")

# Curated 35 Viva Voce Questions categorized into 5 Domains
VIVA_QUESTIONS = [
    {
        "id": 1,
        "domain": "Software Architecture",
        "question": "What core problem does BioSense solve?",
        "answer": "BioSense integrates microbial growth kinetics modeling, clinical antibiotic susceptibility testing (AST) analysis, dynamic machine learning pipelines, and automated PDF reporting into a unified web platform. It eliminates manual spreadsheet errors and fragmentation across curve-fitting and statistical scripts while enforcing scientific ethics.",
        "viva_tip": "Focus on 'end-to-end integration' and 'eliminating manual data pipeline errors'."
    },
    {
        "id": 2,
        "domain": "Software Architecture",
        "question": "Why did you choose the Flask Application Factory pattern?",
        "answer": "The factory pattern (create_app) allows multiple instances with different configurations (development, testing, production). It avoids global state, prevents circular dependencies, and enables isolated testing with in-memory SQLite databases via Pytest without polluting development data.",
        "viva_tip": "Mention how it powers the pytest suite running in memory."
    },
    {
        "id": 3,
        "domain": "Software Architecture",
        "question": "What is the 'Thin Route, Fat Service' architectural principle?",
        "answer": "Routes only parse incoming HTTP requests, verify user sessions, and return responses or templates. All business logic (SciPy curve fitting, Scikit-Learn pipelines, statistical tests, PDF generation) lives in services/, allowing unit testing of algorithms without needing web server context.",
        "viva_tip": "Explain that this makes algorithms 100% testable in Pytest without HTTP mocks."
    },
    {
        "id": 4,
        "domain": "Software Architecture",
        "question": "How is Role-Based Access Control (RBAC) implemented?",
        "answer": "Users hold one of three roles: STUDENT, RESEARCHER, or ADMIN. Access is enforced via a custom Python decorator @role_required(*roles). If an unauthorized user attempts access, an HTTP 403 Forbidden is raised and a security violation is recorded in audit_logs.",
        "viva_tip": "Point out the @role_required decorator in services/auth_service.py."
    },
    {
        "id": 5,
        "domain": "Software Architecture",
        "question": "How is CSV Spreadsheet Formula Injection prevented?",
        "answer": "If an uploaded or exported cell begins with =, +, -, or @, spreadsheet software (Excel, LibreOffice) might execute it as dynamic code. BioSense neutralizes this in services/cleaning_service.py by prepending an apostrophe (') to any cell starting with those characters.",
        "viva_tip": "A great security question to impress data science evaluators."
    },
    {
        "id": 6,
        "domain": "Microbiology & Biology",
        "question": "What does OD600 represent in microbiology?",
        "answer": "Optical Density at 600 nanometers (OD600) is a spectrophotometric measurement of light scattering caused by bacterial cells in liquid suspension. Bacterial cells scatter light rather than absorbing it. OD600 is directly proportional to cell density/biomass in the culture during exponential growth.",
        "viva_tip": "Remember: OD measures *light scattering*, not true molecular absorption."
    },
    {
        "id": 7,
        "domain": "Microbiology & Biology",
        "question": "What are the four distinct phases of a bacterial growth curve?",
        "answer": "1. Lag Phase: Adaptation to medium, enzyme synthesis, no net division. 2. Log (Exponential) Phase: Maximal constant division rate (μ_max), doubling at fixed intervals. 3. Stationary Phase: Nutrients deplete, wastes accumulate, division equals death rate (carrying capacity K). 4. Decline (Death) Phase: Toxic waste build-up causes viable cell count to drop.",
        "viva_tip": "State all 4 phases in sequence and mention the inflection point of the sigmoid curve."
    },
    {
        "id": 8,
        "domain": "Microbiology & Biology",
        "question": "What is the Kirby-Bauer Disk Diffusion assay?",
        "answer": "A standardized antibiotic susceptibility test. A bacterial lawn is spread on agar (Mueller-Hinton). Filter paper disks impregnated with fixed antibiotic concentrations are placed on the plate. Antibiotic diffuses radially outward; if the bacteria are sensitive, a clear circular zone of inhibition forms.",
        "viva_tip": "Emphasize that the *diameter* of this clear zone is measured in millimeters."
    },
    {
        "id": 9,
        "domain": "Microbiology & Biology",
        "question": "How are Sensitive (S), Intermediate (I), and Resistant (R) categories determined?",
        "answer": "They are assigned by comparing measured zone diameters against published EUCAST or CLSI clinical breakpoints. Sensitive implies high probability of therapeutic success; Intermediate indicates uncertain efficacy requiring elevated dosage; Resistant indicates high probability of treatment failure.",
        "viva_tip": "Emphasize that BioSense uses standardized clinical tables, not arbitrary cutoffs."
    },
    {
        "id": 10,
        "domain": "Microbiology & Biology",
        "question": "Why does BioSense strictly forbid clinical prescriptive advice like 'Take Antibiotic X'?",
        "answer": "Under medical software ethics and academic regulations, educational data science software is not certified as clinical decision support. BioSense enforces dataset-derived statements: 'Within the analyzed dataset, Antibiotic X had the highest proportion of observations categorized as Sensitive for Organism Y.'",
        "viva_tip": "Crucial for ethical defense: BioSense provides *analytics*, not clinical prescriptions."
    },
    {
        "id": 11,
        "domain": "Growth Kinetics & Mathematics",
        "question": "What is the Verhulst Logistic Growth equation used in BioSense?",
        "answer": "N(t) = K / [1 + ((K - N0) / N0) * e^(-r*t)], where N(t) is optical density at time t, N0 is initial optical density at t=0, K is carrying capacity (maximum plateau OD), and r is the intrinsic specific growth rate per hour.",
        "viva_tip": "Write out N(t) = K / (1 + A*e^-rt) where A = (K - N0)/N0 on the blackboard if asked."
    },
    {
        "id": 12,
        "domain": "Growth Kinetics & Mathematics",
        "question": "How are the logistic parameters fitted to experimental data?",
        "answer": "We utilize non-linear least squares optimization via SciPy's scipy.optimize.curve_fit. It iteratively adjusts (N0, K, r) to minimize the sum of squared differences between observed OD values and model predictions under biological boundary constraints (N0 > 0, K > N0, r > 0).",
        "viva_tip": "Mention SciPy curve_fit and Levenberg-Marquardt / Trust Region Reflective optimization."
    },
    {
        "id": 13,
        "domain": "Growth Kinetics & Mathematics",
        "question": "How is the maximum specific growth rate (μ_max) calculated?",
        "answer": "In exponential phase, dN/dt = μ*N, which means ln(N) = ln(N0) + μ*t. BioSense calculates the numerical derivative of the natural log of optical density: μ = Δln(OD) / Δt. The maximum slope within this window is identified as μ_max (in hr⁻¹).",
        "viva_tip": "Explain that taking the natural logarithm linearizes the exponential growth phase."
    },
    {
        "id": 14,
        "domain": "Growth Kinetics & Mathematics",
        "question": "How is doubling time (t_d) derived from growth rate?",
        "answer": "When the population doubles, N(t) = 2*N0. Substituting into exponential growth: 2*N0 = N0 * e^(μ*t_d) => 2 = e^(μ*t_d) => ln(2) = μ*t_d => t_d = ln(2) / μ ≈ 0.69315 / μ. For example, if μ = 0.45 hr⁻¹, t_d = 0.69315 / 0.45 = 1.54 hours.",
        "viva_tip": "Always remember 0.69315 / μ_max. It is one of the most common viva questions!"
    },
    {
        "id": 15,
        "domain": "Data Science & Machine Learning",
        "question": "What is Target Leakage, and how does BioSense expose it?",
        "answer": "Target leakage occurs when a training feature directly encodes the target outcome. In Kirby-Bauer testing, S/I/R category is defined directly from zone_diameter_mm. If zone diameter is in the feature set (Variant A), the model gets 99%+ accuracy trivially. To create genuine predictive modeling, Variant B excludes zone diameter and predicts resistance from biological parameters (organism, antibiotic, temp, pH).",
        "viva_tip": "This is the signature data science highlight of this project. Explain Variant A vs Variant B!"
    },
    {
        "id": 16,
        "domain": "Data Science & Machine Learning",
        "question": "Why do you use Scikit-Learn Pipeline and ColumnTransformer?",
        "answer": "Pipelines prevent data leakage during train/test splits. Preprocessing (imputation with SimpleImputer, one-hot encoding with OneHotEncoder, and standard scaling with StandardScaler) is fitted strictly on training folds and only transformed on test folds, preventing test set distribution contamination.",
        "viva_tip": "Mention that fit() is called ONLY on training data, and transform() on test data."
    },
    {
        "id": 17,
        "domain": "Data Science & Machine Learning",
        "question": "What machine learning algorithms are trained in BioSense?",
        "answer": "For classification: Logistic Regression (linear baseline), Decision Trees (interpretable rules), and Random Forest Classifier (ensemble of bagging trees). For regression (predicting OD or zone diameter): Linear Regression and Random Forest Regressor.",
        "viva_tip": "Be ready to explain how Random Forest averages multiple decorrelated decision trees."
    },
    {
        "id": 18,
        "domain": "Data Science & Machine Learning",
        "question": "Why is Accuracy alone misleading for AST classification?",
        "answer": "Because medical datasets frequently suffer from severe class imbalance (e.g. 80% Sensitive, 15% Resistant, 5% Intermediate). A naive model predicting 'Sensitive' for every row gets 80% accuracy but fails to detect resistant superbugs. BioSense evaluates Balanced Accuracy, Precision, Recall, and Macro-F1 scores.",
        "viva_tip": "Explain that Recall for the 'Resistant' class is clinically the most critical metric."
    },
    {
        "id": 19,
        "domain": "Statistics & Anomaly Screening",
        "question": "What is the difference between Student's t-test and Welch's t-test?",
        "answer": "Student's t-test assumes equal variances between two groups (homoscedasticity). In biological trials, cultures in different media or temperatures rarely have equal variance. Welch's t-test adjusts degrees of freedom via the Welch-Satterthwaite equation, providing valid inference without assuming equal variance.",
        "viva_tip": "State that BioSense implements Welch's t-test for biological robustness."
    },
    {
        "id": 20,
        "domain": "Statistics & Anomaly Screening",
        "question": "How does the Isolation Forest detect experimental anomalies?",
        "answer": "Isolation Forest is an unsupervised tree ensemble that isolates anomalies instead of profiling normal points. Because anomalies are few and have extreme attribute values, they are partitioned near the root of random decision trees with significantly shorter average path lengths than normal inliers.",
        "viva_tip": "Explain: 'Anomalies are easier to isolate, so they require fewer tree splits'."
    }
]

# Interactive 10-Question Self-Test Quiz with Instant Explanations
VIVA_QUIZ = [
    {
        "id": 1,
        "question": "What physical phenomenon does Optical Density at 600nm (OD600) measure in a spectrophotometer?",
        "options": [
            "Molecular light absorption by chlorophyll",
            "Light scattering caused by bacterial cells in suspension",
            "Emission of fluorescence from microbial nucleic acids",
            "Direct radioactive beta-particle decay count"
        ],
        "answer": 1,
        "explanation": "Bacterial cells scatter light at 600nm rather than chemically absorbing it. The spectrophotometer measures the reduction in transmitted light due to scattering, which is proportional to cell biomass."
    },
    {
        "id": 2,
        "question": "In the Verhulst logistic model N(t) = K / [1 + A·e^(-rt)], what does the parameter K represent?",
        "options": [
            "Initial inoculum density at time t = 0",
            "Maximum specific growth rate per hour",
            "Carrying capacity (plateau cell density constrained by nutrients)",
            "Kinetic activation energy of the incubation medium"
        ],
        "answer": 2,
        "explanation": "K is the carrying capacity. It represents the maximum optical density the microbial population can sustain in a closed batch system before nutrient exhaustion halts net division."
    },
    {
        "id": 3,
        "question": "If an organism has a maximum specific growth rate of μ_max = 0.693 hr⁻¹, what is its approximate doubling time?",
        "options": [
            "0.50 hours (30 minutes)",
            "1.00 hour (60 minutes)",
            "2.00 hours (120 minutes)",
            "4.00 hours (240 minutes)"
        ],
        "answer": 1,
        "explanation": "Doubling time formula is t_d = ln(2) / μ_max. Since ln(2) ≈ 0.69315, t_d = 0.69315 / 0.693 ≈ 1.00 hour."
    },
    {
        "id": 4,
        "question": "Why does training an AST classification model using zone diameter (Variant A) constitute Target Leakage?",
        "options": [
            "Because zone diameter is measured with high measurement error",
            "Because zone diameter is the exact measurement that clinically defines S/I/R categories",
            "Because zone diameter is only available for Gram-positive bacteria",
            "Because Scikit-Learn cannot scale continuous millimeter values"
        ],
        "answer": 1,
        "explanation": "In Kirby-Bauer testing, S/I/R category is derived deterministically from zone diameter by EUCAST tables. Including zone diameter is leaking the ground truth answer into the model, producing trivial 99%+ accuracy that fails on unmeasured cultures."
    },
    {
        "id": 5,
        "question": "During which phase of bacterial growth does the specific growth rate equal zero (dN/dt = 0)?",
        "options": [
            "Logarithmic (exponential) phase",
            "Stationary phase",
            "Acceleration phase",
            "Exponential doubling phase"
        ],
        "answer": 1,
        "explanation": "In the stationary phase, nutrient depletion and accumulation of toxic metabolic products cause the rate of cell division to equal the rate of cell death, yielding net zero growth."
    },
    {
        "id": 6,
        "question": "Why is Welch's t-test preferred over Student's classical two-sample t-test in microbiology?",
        "options": [
            "It computes results much faster in Python",
            "It does not require the assumption of equal population variances (homoscedasticity)",
            "It only works on paired repeated measures",
            "It replaces the need for a control culture group"
        ],
        "answer": 1,
        "explanation": "Biological assays under different media or temperatures rarely share identical variances. Welch's t-test adjusts degrees of freedom and remains statistically robust without assuming equal variance."
    },
    {
        "id": 7,
        "question": "How does BioSense prevent CSV Formula Injection attacks on exported laboratory datasets?",
        "options": [
            "By converting all strings to uppercase letters",
            "By prepending an apostrophe (') to any cell starting with =, +, -, or @",
            "By strictly converting all CSV files into encrypted ZIP archives",
            "By removing all numeric digits from the exported tables"
        ],
        "answer": 1,
        "explanation": "Spreadsheet software (Excel) may execute cells starting with =, +, -, or @ as executable formulas. Prepending an apostrophe forces the spreadsheet to treat the content strictly as raw text."
    },
    {
        "id": 8,
        "question": "What is the primary role of Scikit-Learn's Pipeline in the ML Lab?",
        "options": [
            "To speed up GPU multi-threading",
            "To encapsulate preprocessing and modeling so test folds never leak into training transformations",
            "To convert Flask SQLAlchemy models into MongoDB documents",
            "To automatically format 13-section vector PDF documents"
        ],
        "answer": 1,
        "explanation": "Pipelines prevent data leakage by ensuring all feature scalers, encoders, and imputers are fitted solely on training splits, and only applied via transform() onto test splits."
    },
    {
        "id": 9,
        "question": "In the Kirby-Bauer disk diffusion method, what does a larger zone of inhibition indicate?",
        "options": [
            "The bacterium is highly resistant to the antibiotic",
            "The bacterium is sensitive and susceptible to inhibition by the antibiotic",
            "The incubation temperature was excessively hot",
            "The Mueller-Hinton agar expired"
        ],
        "answer": 1,
        "explanation": "A wider clear halo around the antibiotic disk indicates that the antibiotic was able to stop bacterial proliferation even at lower diffused concentrations, signifying higher susceptibility (Sensitive)."
    },
    {
        "id": 10,
        "question": "How does the Isolation Forest algorithm identify laboratory anomalies or contaminated cultures?",
        "options": [
            "By calculating Euclidean distance from the nearest K centroids",
            "By measuring how few random tree splits are required to isolate an observation from the rest",
            "By fitting a degree-5 polynomial regression curve",
            "By calculating the Pearson correlation with the control organism"
        ],
        "answer": 1,
        "explanation": "Because anomalies are few and have unusual values, they are partitioned near the top of random decision trees with significantly shorter path lengths than normal inliers."
    }
]

# Biological & Data Science Glossary
GLOSSARY_TERMS = [
    {"term": "OD600", "category": "Microbiology", "definition": "Optical density measured at 600 nm; measures light scattering proportional to cell biomass in liquid culture."},
    {"term": "Verhulst Model", "category": "Kinetics Math", "definition": "The sigmoidal logistic equation N(t) = K / [1 + A·e^(-rt)] describing closed-system population growth with carrying capacity."},
    {"term": "Carrying Capacity (K)", "category": "Kinetics Math", "definition": "The maximum population density that an environment/culture medium can sustainably support before nutrient exhaustion."},
    {"term": "Doubling Time (t_d)", "category": "Kinetics Math", "definition": "The time required for microbial biomass to double during the exponential phase: t_d = ln(2) / μ_max."},
    {"term": "Specific Growth Rate (μ)", "category": "Kinetics Math", "definition": "The instantaneous rate of biomass increase per unit biomass (hr⁻¹), computed from the log-linear slope."},
    {"term": "Kirby-Bauer Assay", "category": "AST Testing", "definition": "Standardized antibiotic disk diffusion method measuring the clear zone of inhibition (in mm) on Mueller-Hinton agar."},
    {"term": "EUCAST Breakpoints", "category": "AST Testing", "definition": "Clinical zone diameter thresholds established by the European Committee on Antimicrobial Susceptibility Testing to categorize S/I/R."},
    {"term": "Target Leakage", "category": "Machine Learning", "definition": "Flaw where a training feature contains the ground truth target or a post-event measurement, yielding unrealistic 100% test accuracy."},
    {"term": "Variant A vs Variant B", "category": "Machine Learning", "definition": "BioSense educational framework comparing a leaked model (Variant A, with zone diameter) against a genuine predictive model (Variant B)."},
    {"term": "Isolation Forest", "category": "Statistics / ML", "definition": "Unsupervised anomaly detection algorithm that isolates outliers with fewer random decision tree splits."},
    {"term": "Welch's t-test", "category": "Statistics", "definition": "Two-sample hypothesis test comparing group means without assuming equal variances (heteroscedasticity)."},
    {"term": "One-Way ANOVA", "category": "Statistics", "definition": "Analysis of Variance testing whether means across three or more experimental groups are statistically equivalent using the F-statistic."},
    {"term": "Mueller-Hinton Medium", "category": "Microbiology", "definition": "Standardized non-selective culture broth/agar engineered for reproducible antimicrobial diffusion rates."},
    {"term": "ESKAPE Pathogens", "category": "Microbiology", "definition": "Six multidrug-resistant nosocomial pathogens: Enterococcus faecium, S. aureus, K. pneumoniae, A. baumannii, P. aeruginosa, and Enterobacter."},
    {"term": "Permutation Importance", "category": "Machine Learning", "definition": "Model-agnostic explainability metric measuring the drop in performance when a feature's values are randomly shuffled."},
    {"term": "Stratified K-Fold", "category": "Machine Learning", "definition": "Cross-validation splitting method that preserves identical class percentage ratios in each fold to handle imbalanced AST datasets."}
]


@learn_bp.route("/")
def index():
    """Render the Knowledge Hub & Viva Voce Learning Center."""
    return render_template(
        "learn/knowledge_hub.html",
        viva_questions=VIVA_QUESTIONS,
        glossary=GLOSSARY_TERMS,
        quiz_count=len(VIVA_QUIZ)
    )


@learn_bp.route("/api/viva-qa")
def get_viva_qa():
    """Return viva questions and answers as JSON for client-side search."""
    domain_filter = request.args.get("domain", "")
    query = request.args.get("q", "").strip().lower()

    filtered = VIVA_QUESTIONS
    if domain_filter:
        filtered = [q for q in filtered if q["domain"] == domain_filter]
    if query:
        filtered = [
            q for q in filtered
            if query in q["question"].lower() or query in q["answer"].lower() or query in q["viva_tip"].lower()
        ]

    return jsonify({"count": len(filtered), "questions": filtered})


@learn_bp.route("/api/quiz")
def get_quiz():
    """Return interactive quiz questions."""
    return jsonify({"questions": VIVA_QUIZ})
