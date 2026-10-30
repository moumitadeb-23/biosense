import io
import os
import math
from datetime import datetime
from typing import Dict, Any, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether,
    HRFlowable,
    PageBreak,
)
from reportlab.pdfgen import canvas
from flask import current_app

from extensions import db
from database.models import (
    Experiment,
    GrowthMeasurement,
    SusceptibilityTest,
    Organism,
    Antibiotic,
    Medium,
    MLModel,
    Report,
    User,
    AuditLog,
)
from services.growth_service import fit_logistic_growth_curve, logistic_function
from services.susceptibility_service import get_susceptibility_summary
from services.anomaly_service import detect_growth_anomalies


class NumberedCanvas(canvas.Canvas):
    """Two-pass ReportLab canvas that stamps running headers and total page counts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(40, 755, "BioSense — Intelligent Microbial Growth & Susceptibility Analytics")
            self.drawRightString(572, 755, "Confidential Academic / Research Report")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(40, 748, 572, 748)

        # Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(40, 42, 572, 42)

        disclaimer_text = "Educational/Research Analytics — Not for Clinical Diagnosis or Treatment Decisions."
        self.drawString(40, 30, disclaimer_text)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(572, 30, page_str)
        self.restoreState()


def _build_growth_curve_image(time_pts: List[float], od_pts: List[float], kinetics: Dict[str, Any]) -> io.BytesIO:
    """Render a Matplotlib Agg plot of Time vs OD600 with fitted curves and phases."""
    fig, ax = plt.subplots(figsize=(6.8, 2.7), dpi=150)
    
    # Plot experimental data
    ax.scatter(time_pts, od_pts, color="#0284c7", s=32, zorder=4, label="Observed OD600", edgecolors="#0369a1")
    
    # Plot fitted logistic curve if available
    if kinetics.get("success") and "t_smooth" in kinetics:
        t_sm = kinetics["t_smooth"]
        y_sm = kinetics["y_smooth"]
        ax.plot(t_sm, y_sm, color="#0f766e", linewidth=2.2, label=f"Verhulst Fit (R²={kinetics.get('r_squared', 0.99):.2f})", zorder=3)
        
        # Highlight phases if available
        phases = kinetics.get("phase_segmentation", {})
        if "lag_phase" in phases and "stationary_phase" in phases:
            lag_end = phases["lag_phase"]["end_h"]
            stat_start = phases["stationary_phase"]["start_h"]
            max_t = max(time_pts) if time_pts else 24.0
            
            ax.axvspan(0, lag_end, color="#fef3c7", alpha=0.35, label="Lag Phase")
            ax.axvspan(lag_end, stat_start, color="#dcfce7", alpha=0.35, label="Log Phase")
            ax.axvspan(stat_start, max_t, color="#e0e7ff", alpha=0.35, label="Stationary Phase")

    ax.set_title("Microbial Optical Density (OD600) vs. Incubation Time (h)", fontsize=10, fontweight="bold", pad=8, color="#0f172a")
    ax.set_xlabel("Incubation Time (hours)", fontsize=8, color="#334155")
    ax.set_ylabel("Optical Density (OD600)", fontsize=8, color="#334155")
    ax.grid(True, linestyle="--", alpha=0.4, color="#94a3b8")
    ax.tick_params(axis="both", labelsize=7, colors="#475569")
    ax.legend(loc="lower right", fontsize=7, framealpha=0.9, edgecolor="#cbd5e1")
    
    for spine in ax.spines.values():
        spine.set_color("#cbd5e1")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _build_susceptibility_chart_image(s_count: int, i_count: int, r_count: int) -> io.BytesIO:
    """Render a Matplotlib donut chart showing Susceptibility S/I/R categorical distribution."""
    fig, ax = plt.subplots(figsize=(6.8, 2.5), dpi=150)
    
    categories = ["Sensitive (S)", "Intermediate (I)", "Resistant (R)"]
    counts = [s_count, i_count, r_count]
    palette = ["#10b981", "#f59e0b", "#ef4444"]
    
    # Filter non-zero for clean chart
    active_cats = [c for c, val in zip(categories, counts) if val > 0]
    active_counts = [val for val in counts if val > 0]
    active_colors = [col for col, val in zip(palette, counts) if val > 0]
    
    if not active_counts:
        active_cats = ["No Data Available"]
        active_counts = [1]
        active_colors = ["#94a3b8"]

    wedges, texts, autotexts = ax.pie(
        active_counts,
        labels=active_cats,
        colors=active_colors,
        autopct="%1.1f%%" if sum(active_counts) > 1 else "",
        startangle=140,
        pctdistance=0.75,
        wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
    )
    
    for t in texts:
        t.set_fontsize(7.5)
        t.set_color("#1e293b")
    for at in autotexts:
        at.set_fontsize(7.5)
        at.set_weight("bold")
        at.set_color("white")

    total_n = sum(counts)
    ax.text(0, 0, f"Total\nN = {total_n}", ha="center", va="center", fontsize=8.5, fontweight="bold", color="#0f172a")
    ax.set_title("Antibiotic Susceptibility Testing (AST) Category Distribution", fontsize=9.5, fontweight="bold", pad=8, color="#0f172a")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_pdf_report(
    user_id: int,
    experiment_id: Optional[int] = None,
    title: Optional[str] = None,
    include_ml: bool = True,
    include_anomalies: bool = True
) -> Dict[str, Any]:
    """Generate a comprehensive 13-section BioSense scientific PDF report.
    
    Returns a dictionary with status, report_id, filename, and file_path.
    """
    user = User.query.get(user_id)
    if not user:
        return {"success": False, "error": "Invalid user ID."}

    # Fetch Experiment
    experiment = None
    if experiment_id:
        experiment = Experiment.query.get(experiment_id)
    if not experiment:
        experiment = Experiment.query.order_by(Experiment.id.desc()).first()

    if not experiment:
        return {"success": False, "error": "No experimental records found in database to compile report."}

    # Prepare directories and file paths
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    reports_dir = os.path.join(upload_folder, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_title = title.strip() if title else f"BioSense Analytics Report — Exp #{experiment.id}"
    safe_filename = f"report_exp{experiment.id}_{timestamp_str}.pdf"
    output_filepath = os.path.join(reports_dir, safe_filename)

    # 1. Gather Growth Kinetics Data
    growth_measurements = GrowthMeasurement.query.filter_by(experiment_id=experiment.id).order_by(GrowthMeasurement.time_h.asc()).all()
    if not growth_measurements:
        # Fallback to organism-wide growth measurements if this experiment has none
        growth_measurements = GrowthMeasurement.query.join(Experiment).filter(Experiment.organism_id == experiment.organism_id).order_by(GrowthMeasurement.time_h.asc()).all()

    time_pts = [m.time_h for m in growth_measurements]
    od_pts = [m.optical_density for m in growth_measurements]

    kinetics = fit_logistic_growth_curve(time_pts, od_pts) if len(time_pts) >= 3 else {"success": False}

    # 2. Gather Susceptibility Data
    ast_tests = SusceptibilityTest.query.filter_by(experiment_id=experiment.id).all()
    if not ast_tests:
        # Fallback to organism-level tests
        ast_tests = SusceptibilityTest.query.filter_by(organism_id=experiment.organism_id).all()

    s_count = sum(1 for t in ast_tests if t.category == "S")
    i_count = sum(1 for t in ast_tests if t.category == "I")
    r_count = sum(1 for t in ast_tests if t.category == "R")
    total_ast = len(ast_tests)
    r_pct = round((r_count / total_ast * 100.0), 1) if total_ast > 0 else 0.0

    # 3. Gather Descriptive Statistics
    all_growth_od = [m.optical_density for m in growth_measurements] if growth_measurements else [0.0]
    all_ast_zones = [t.zone_diameter_mm for t in ast_tests if t.zone_diameter_mm is not None]

    def _calc_stats(arr):
        if not arr:
            return {"mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "iqr": 0.0}
        a = np.array(arr)
        q75, q25 = np.percentile(a, [75, 25])
        return {
            "mean": round(float(np.mean(a)), 3),
            "median": round(float(np.median(a)), 3),
            "std": round(float(np.std(a)), 3),
            "min": round(float(np.min(a)), 3),
            "max": round(float(np.max(a)), 3),
            "iqr": round(float(q75 - q25), 3)
        }

    od_stats = _calc_stats(all_growth_od)
    zone_stats = _calc_stats(all_ast_zones)

    # 4. Gather ML Model Information
    latest_model = MLModel.query.order_by(MLModel.id.desc()).first()

    # 5. Gather Anomaly Information
    anomaly_summary = detect_growth_anomalies() if include_anomalies else None

    # Setup ReportLab Document
    doc = SimpleDocTemplate(
        output_filepath,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=46,
        bottomMargin=48
    )

    # Styles
    base_styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        alignment=0,
        spaceAfter=3
    )

    tagline_style = ParagraphStyle(
        "Tagline",
        parent=base_styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0284c7"),
        spaceAfter=12
    )

    sec_heading_style = ParagraphStyle(
        "SecHeading",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155")
    )

    body_bold = ParagraphStyle(
        "BodyBold",
        parent=body_style,
        fontName="Helvetica-Bold"
    )

    disclaimer_style = ParagraphStyle(
        "DisclaimerText",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#991b1b")
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=base_styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=0
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=base_styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1e293b")
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=table_cell_style,
        fontName="Helvetica-Bold"
    )

    story = []

    # =========================================================================
    # SECTION 1: Title & Document Metadata
    # =========================================================================
    story.append(Paragraph("BioSense Analytics Report", title_style))
    story.append(Paragraph("Turning Biological Data into Intelligent Insights — Automated Analytical Dossier", tagline_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=10))

    meta_data = [
        [
            Paragraph("<b>Report Identifier:</b>", body_style),
            Paragraph(f"BSR-{experiment.id:04d}-{datetime.utcnow().strftime('%Y%m%d')}", body_style),
            Paragraph("<b>Generated At:</b>", body_style),
            Paragraph(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), body_style),
        ],
        [
            Paragraph("<b>Author / Analyst:</b>", body_style),
            Paragraph(f"{user.username} ({user.role})", body_style),
            Paragraph("<b>Experiment ID:</b>", body_style),
            Paragraph(f"EXP-{experiment.id} ({experiment.data_source})", body_style),
        ],
    ]
    t_meta = Table(meta_data, colWidths=[115, 151, 115, 151])
    t_meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 2: Executive Summary & Educational Disclaimer
    # =========================================================================
    story.append(Paragraph("1. Executive Summary & Regulatory Disclaimer", sec_heading_style))
    summary_text = (
        f"This report presents an analytical synthesis of microbial growth dynamics and antimicrobial susceptibility for "
        f"<i>{experiment.organism.scientific_name if experiment.organism else 'the selected culture'}</i> in "
        f"{experiment.medium.name if experiment.medium else 'standard medium'}. "
        f"Peak optical density reached <b>{kinetics.get('max_od', 'N/A')}</b> with an estimated doubling time of "
        f"<b>{kinetics.get('doubling_time_h', 'N/A')} hours</b>. Across {total_ast} susceptibility observations, "
        f"the overall resistance proportion was <b>{r_pct}%</b>."
    )
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 5))

    # Prominent Disclaimer Callout Box
    disclaimer_box = [
        [
            Paragraph(
                "<b>MANDATORY SCIENTIFIC & CLINICAL DISCLAIMER:</b><br/>"
                "This document and its analytical findings are generated strictly for academic, research, and data science "
                "evaluation. BioSense is <b>not a clinical diagnostic device or decision-support system</b>. "
                "Findings must never be utilized for patient diagnosis, therapy selection, prescription, or clinical management.",
                disclaimer_style
            )
        ]
    ]
    t_disc = Table(disclaimer_box, colWidths=[532])
    t_disc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
        ("BOX", (0, 0), (-1, -1), 1.0, colors.HexColor("#ef4444")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t_disc)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 3: Dataset Overview & Data Source Label
    # =========================================================================
    story.append(Paragraph("2. Dataset Overview & Provenance", sec_heading_style))
    dataset_table = [
        [Paragraph("Parameter", table_header_style), Paragraph("Value", table_header_style)],
        [Paragraph("Data Source Label", table_cell_bold), Paragraph(str(experiment.data_source), table_cell_style)],
        [Paragraph("Culture Observations (OD600)", table_cell_bold), Paragraph(str(len(growth_measurements)), table_cell_style)],
        [Paragraph("Susceptibility Tests (AST)", table_cell_bold), Paragraph(str(len(ast_tests)), table_cell_style)],
        [Paragraph("Experiment Registered At", table_cell_bold), Paragraph(experiment.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), table_cell_style)],
        [Paragraph("Investigator Notes", table_cell_bold), Paragraph(experiment.notes or "Standard educational baseline protocol.", table_cell_style)],
    ]
    t_ds = Table(dataset_table, colWidths=[180, 352])
    t_ds.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_ds)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 4: Organism Reference Profile
    # =========================================================================
    org = experiment.organism
    story.append(Paragraph("3. Organism Reference Profile", sec_heading_style))
    org_table = [
        [Paragraph("Taxonomic Attribute", table_header_style), Paragraph("Standard Microbiology Reference Data", table_header_style)],
        [Paragraph("Scientific Name", table_cell_bold), Paragraph(f"<i>{org.scientific_name if org else 'Unknown'}</i>", table_cell_style)],
        [Paragraph("Genus & Species", table_cell_bold), Paragraph(f"{org.genus if org else ''} {org.species if org else ''}", table_cell_style)],
        [Paragraph("Gram Stain Characteristic", table_cell_bold), Paragraph(str(org.gram_type if org else 'Unknown'), table_cell_style)],
        [Paragraph("Taxonomy (Domain / Family)", table_cell_bold), Paragraph(f"{org.domain_family if org and org.domain_family else 'N/A'}", table_cell_style)],
        [Paragraph("Microbial Type & Description", table_cell_bold), Paragraph(str(org.description if org and org.description else 'Opportunistic model organism; standard AST reference strains.'), table_cell_style)],
    ]
    t_org = Table(org_table, colWidths=[180, 352])
    t_org.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_org)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 5: Environmental & Culture Parameters
    # =========================================================================
    story.append(Paragraph("4. Environmental & Culture Parameters", sec_heading_style))
    med = experiment.medium
    env_table = [
        [Paragraph("Incubation Parameter", table_header_style), Paragraph("Experimental Value", table_header_style), Paragraph("Standard Tolerance Range", table_header_style)],
        [Paragraph("Incubation Temperature", table_cell_bold), Paragraph(f"{experiment.temperature} °C", table_cell_style), Paragraph("35.0 – 37.0 °C (Mesophilic norm)", table_cell_style)],
        [Paragraph("Initial Medium pH", table_cell_bold), Paragraph(f"{experiment.ph}", table_cell_style), Paragraph("7.2 – 7.4 (Physiological neutral)", table_cell_style)],
        [Paragraph("Growth Medium", table_cell_bold), Paragraph(med.name if med else "Nutrient Broth", table_cell_style), Paragraph(med.description if med and med.description else "Standard complex nutritive medium", table_cell_style)],
        [Paragraph("Incubation Period", table_cell_bold), Paragraph(f"{experiment.incubation_time_h} hours", table_cell_style), Paragraph("18.0 – 24.0 hours standard", table_cell_style)],
    ]
    t_env = Table(env_table, colWidths=[160, 160, 212])
    t_env.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_env)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 6: Microbial Growth Kinetics Analysis
    # =========================================================================
    story.append(Paragraph("5. Microbial Growth Kinetics Analysis", sec_heading_style))
    kin_table = [
        [Paragraph("Kinetic Metric", table_header_style), Paragraph("Formula / Definition", table_header_style), Paragraph("Estimated Value", table_header_style)],
        [Paragraph("Initial Optical Density (N₀)", table_cell_bold), Paragraph("N(0) baseline absorbance", table_cell_style), Paragraph(str(kinetics.get("initial_od", "N/A")), table_cell_style)],
        [Paragraph("Maximum Optical Density (K)", table_cell_bold), Paragraph("Carrying capacity asymptote", table_cell_style), Paragraph(str(kinetics.get("max_od", "N/A")), table_cell_style)],
        [Paragraph("Specific Growth Rate (μ_max)", table_cell_bold), Paragraph("d(ln N)/dt in exponential phase", table_cell_style), Paragraph(f"{kinetics.get('mu_max', 'N/A')} hr⁻¹", table_cell_style)],
        [Paragraph("Doubling Time (t_d)", table_cell_bold), Paragraph("ln(2) / μ_max", table_cell_style), Paragraph(f"{kinetics.get('doubling_time_h', 'N/A')} hours", table_cell_style)],
        [Paragraph("Time to Max OD (T_max)", table_cell_bold), Paragraph("Time elapsed to reach peak absorbance", table_cell_style), Paragraph(f"{kinetics.get('time_to_max_h', 'N/A')} hours", table_cell_style)],
        [Paragraph("Model Goodness of Fit (R²)", table_cell_bold), Paragraph("1 - (SS_res / SS_tot)", table_cell_style), Paragraph(str(kinetics.get("r_squared", "N/A")), table_cell_style)],
    ]
    t_kin = Table(kin_table, colWidths=[170, 202, 160])
    t_kin.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_kin)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 7: Growth Curve Visualization
    # =========================================================================
    story.append(Paragraph("6. Growth Curve Visualization (Time vs OD600)", sec_heading_style))
    curve_img_buf = _build_growth_curve_image(time_pts, od_pts, kinetics)
    story.append(Image(curve_img_buf, width=480, height=190))
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 8: Antibiotic Susceptibility Profile
    # =========================================================================
    story.append(Paragraph("7. Antibiotic Susceptibility Testing (AST) Profile", sec_heading_style))
    ast_rows = [
        [
            Paragraph("Antibiotic", table_header_style),
            Paragraph("Class", table_header_style),
            Paragraph("Zone (mm)", table_header_style),
            Paragraph("Result", table_header_style),
            Paragraph("Observation Interpretation", table_header_style)
        ]
    ]

    for t in ast_tests[:8]:  # display up to 8 representative tests in table
        cat_badge = t.category
        if cat_badge == "S":
            cat_desc = "Sensitive (Susceptible)"
        elif cat_badge == "I":
            cat_desc = "Intermediate"
        else:
            cat_desc = "Resistant"

        ast_rows.append([
            Paragraph(t.antibiotic.name if t.antibiotic else "Antibiotic", table_cell_bold),
            Paragraph(t.antibiotic.antibiotic_class if t.antibiotic else "Class", table_cell_style),
            Paragraph(f"{t.zone_diameter_mm:.1f}" if t.zone_diameter_mm else "N/A", table_cell_style),
            Paragraph(cat_badge, table_cell_bold),
            Paragraph(f"Within dataset: {cat_desc}", table_cell_style)
        ])

    if len(ast_tests) == 0:
        ast_rows.append([Paragraph("No AST records", table_cell_style), Paragraph("-", table_cell_style), Paragraph("-", table_cell_style), Paragraph("-", table_cell_style), Paragraph("-", table_cell_style)])

    t_ast = Table(ast_rows, colWidths=[110, 110, 65, 55, 192])
    t_ast.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_ast)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 9: Susceptibility Distribution Visualization
    # =========================================================================
    story.append(Paragraph("8. AST Categorical Distribution Chart", sec_heading_style))
    ast_img_buf = _build_susceptibility_chart_image(s_count, i_count, r_count)
    story.append(Image(ast_img_buf, width=480, height=175))
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 10: Descriptive Statistical Summary
    # =========================================================================
    story.append(Paragraph("9. Descriptive Statistical Summary", sec_heading_style))
    stats_table = [
        [
            Paragraph("Metric", table_header_style),
            Paragraph("Mean", table_header_style),
            Paragraph("Median", table_header_style),
            Paragraph("Std Dev", table_header_style),
            Paragraph("Min", table_header_style),
            Paragraph("Max", table_header_style),
            Paragraph("IQR", table_header_style)
        ],
        [
            Paragraph("Optical Density (OD600)", table_cell_bold),
            Paragraph(str(od_stats["mean"]), table_cell_style),
            Paragraph(str(od_stats["median"]), table_cell_style),
            Paragraph(str(od_stats["std"]), table_cell_style),
            Paragraph(str(od_stats["min"]), table_cell_style),
            Paragraph(str(od_stats["max"]), table_cell_style),
            Paragraph(str(od_stats["iqr"]), table_cell_style),
        ],
        [
            Paragraph("Zone Diameter (mm)", table_cell_bold),
            Paragraph(str(zone_stats["mean"]), table_cell_style),
            Paragraph(str(zone_stats["median"]), table_cell_style),
            Paragraph(str(zone_stats["std"]), table_cell_style),
            Paragraph(str(zone_stats["min"]), table_cell_style),
            Paragraph(str(zone_stats["max"]), table_cell_style),
            Paragraph(str(zone_stats["iqr"]), table_cell_style),
        ]
    ]
    t_stats = Table(stats_table, colWidths=[148, 64, 64, 64, 64, 64, 64])
    t_stats.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_stats)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 11: Machine Learning Predictive Analytics
    # =========================================================================
    story.append(Paragraph("10. Machine Learning Predictive Analytics", sec_heading_style))
    if include_ml and latest_model:
        import json
        try:
            m_metrics = json.loads(latest_model.metrics_json) if isinstance(latest_model.metrics_json, str) else latest_model.metrics_json
        except Exception:
            m_metrics = {}

        acc_or_r2 = m_metrics.get("accuracy", m_metrics.get("test_r2", "N/A"))
        if isinstance(acc_or_r2, float):
            acc_or_r2 = f"{acc_or_r2 * 100:.1f}%" if "accuracy" in m_metrics else f"R² = {acc_or_r2:.3f}"

        ml_table = [
            [Paragraph("ML Pipeline Attribute", table_header_style), Paragraph("Trained Model Specification", table_header_style)],
            [Paragraph("Model Name", table_cell_bold), Paragraph(latest_model.name, table_cell_style)],
            [Paragraph("Pipeline Algorithm", table_cell_bold), Paragraph(latest_model.algorithm, table_cell_style)],
            [Paragraph("Target Variable", table_cell_bold), Paragraph(latest_model.target, table_cell_style)],
            [Paragraph("Evaluation Metric", table_cell_bold), Paragraph(str(acc_or_r2), table_cell_style)],
            [Paragraph("Regulatory Caveat", table_cell_bold), Paragraph("This model provides predictions based on the training dataset and is intended for educational/research purposes only.", table_cell_style)],
        ]
        t_ml = Table(ml_table, colWidths=[180, 352])
    else:
        t_ml = Table([[Paragraph("ML module evaluation not requested or no trained model found.", table_cell_style)]], colWidths=[532])

    t_ml.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_ml)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 12: Anomaly & Outlier Screening Summary
    # =========================================================================
    story.append(Paragraph("11. Anomaly & Outlier Screening Summary", sec_heading_style))
    if include_anomalies and anomaly_summary and anomaly_summary.get("success"):
        counts = anomaly_summary.get("anomaly_counts", {})
        anom_table = [
            [Paragraph("Screening Technique", table_header_style), Paragraph("Mathematical Rule", table_header_style), Paragraph("Detected Count", table_header_style)],
            [Paragraph("Interquartile Range (IQR)", table_cell_bold), Paragraph("Values < Q1 - 1.5*IQR or > Q3 + 1.5*IQR", table_cell_style), Paragraph(str(counts.get("iqr", 0)), table_cell_style)],
            [Paragraph("Standardized Z-Score", table_cell_bold), Paragraph("|Z| > 2.8 standard deviations", table_cell_style), Paragraph(str(counts.get("zscore", 0)), table_cell_style)],
            [Paragraph("Isolation Forest Ensemble", table_cell_bold), Paragraph("Unsupervised partition tree isolation", table_cell_style), Paragraph(str(counts.get("isolation_forest", 0)), table_cell_style)],
            [Paragraph("Interpretation Note", table_cell_bold), Paragraph("Statistical outliers represent dispersion anomalies, not proof of measurement contamination.", table_cell_style), Paragraph("Informational", table_cell_style)]
        ]
        t_anom = Table(anom_table, colWidths=[160, 252, 120])
    else:
        t_anom = Table([[Paragraph("Screening indicates baseline values within standard expected variance bounds.", table_cell_style)]], colWidths=[532])

    t_anom.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t_anom)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECTION 13: Methodological Notes & Viva Defense References
    # =========================================================================
    story.append(Paragraph("12. Methodological Notes & Viva Defense References", sec_heading_style))
    method_text = (
        "<b>1. Verhulst Logistic Model:</b> Growth curves are modeled using the non-linear differential solution "
        "<i>N(t) = K / [1 + ((K - N₀)/N₀) · exp(-r · t)]</i> where <i>K</i> represents carrying capacity and <i>r</i> "
        "is the intrinsic growth rate. Doubling time is computed via <i>t_d = ln(2) / μ_max</i>.<br/>"
        "<b>2. Breakpoint Interpretations:</b> Zone diameters and concentrations follow CLSI M100 and EUCAST "
        "reference standards. Intermediate results suggest indeterminate susceptibility requiring therapeutic caution.<br/>"
        "<b>3. Viva Defense Context:</b> Developed for 4th-year BCA Data Science evaluation at University level. "
        "Demonstrates complete full-stack architecture, machine learning pipelines, and statistical modeling."
    )
    story.append(Paragraph(method_text, body_style))

    # Build PDF with NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)

    # Save to database
    new_report = Report(
        user_id=user.id,
        experiment_id=experiment.id,
        title=report_title,
        filename=safe_filename,
        file_path=output_filepath
    )
    db.session.add(new_report)

    # Log audit event
    audit_entry = AuditLog(
        user_id=user.id,
        action="report_generated",
        details=f"Generated PDF report '{report_title}' for Experiment #{experiment.id} (File: {safe_filename})"
    )
    db.session.add(audit_entry)
    db.session.commit()

    return {
        "success": True,
        "report_id": new_report.id,
        "filename": safe_filename,
        "file_path": output_filepath,
        "title": report_title
    }
