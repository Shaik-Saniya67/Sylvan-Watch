
"""Human-readable analysis reports generated from saved detection results."""

import json
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from sylvan.ml.evaluation import CAVEATS


def build_markdown_report(run_id: str, result: dict, detections: dict) -> str:
    s, m, r = result["summary"], result["model"], result["request"]

    lines = [
        f"# Deforestation analysis report: {run_id}", "",
        "## Request",
        f"- Area (W, S, E, N): {', '.join(f'{v:.5f}' for v in r['bbox'])}",
        f"- Before: {r['before_year']}   After: {r['after_year']}   Season months: {r['season_months'][0]}-{r['season_months'][1]}",
        f"- Model: **{m['name']}** (requested: {r['model_requested']}), decision threshold {m.get('threshold', 0.5)}", "",
        "## Result",
        f"- Detected loss patches: {s['detections']}",
        f"- Estimated forest-cover loss: **{s['loss_area_ha']} ha** ({s['loss_percent_of_forest']}% of {s['forest_area_ha']} ha scanned forest)",
        f"- Cloud-free coverage of the area: {result['data_quality']['cloud_free_coverage_percent']}%", "",
        "## Largest detections",
        "| # | Lon | Lat | Area (ha) | Confidence | Land cover (2021) |",
        "|---|---|---|---|---|---|",
    ]

    for feature in detections.get("features", [])[:20]:
        p = feature["properties"]
        conf = (
            "n/a (rule-based)"
            if p.get("confidence") is None
            else f'{p["confidence"]:.2f}'
        )
        lines.append(
            f'| {p["id"]} | {p["lon"]:.5f} | {p["lat"]:.5f} | '
            f'{p["area_ha"]} | {conf} | {p.get("landcover", "Unknown")} |'
        )

    lines += ["", "## Model evaluation (held-out test sites)"]

    if m.get("evaluated"):
        lines.append(
            f'F1 {m["test_f1"]:.3f}, precision {m["test_precision"]:.3f}, '
            f'recall {m["test_recall"]:.3f}, IoU {m["test_iou"]:.3f}, '
            f'measured against Hansen reference labels '
            f'(metrics generated {m.get("metrics_generated_at", "not recorded")}).'
        )
    else:
        lines.append("No evaluation was recorded for this model; accuracy is unknown.")

    lines += [
        "",
        "## Data sources",
        *(f"- {k}: {v}" for k, v in result.get("datasets", {}).items()),
        "",
        "## Limitations",
        *(f"- {c}" for c in [*result.get("notes", []), *CAVEATS]),
        "",
    ]

    return "\n".join(lines)


def load_run_documents(run_dir: Path) -> tuple[dict, dict]:
    return (
        json.loads((run_dir / "result.json").read_text()),
        json.loads((run_dir / "detections.geojson").read_text()),
    )


def build_pdf_report(
    run_id: str,
    result: dict,
    detections: dict,
    run_dir: Path | None = None,
) -> bytes:
    """Build a PDF report using saved results and optional run-specific images."""

    from PIL import Image as PILImage

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        KeepTogether,
        HRFlowable,
        Image as PDFImage,
    )

    summary = result["summary"]
    model = result["model"]
    request = result["request"]
    quality = result["data_quality"]

    forest = colors.HexColor("#173F35")
    forest_light = colors.HexColor("#EAF2ED")
    accent = colors.HexColor("#B8D8A8")
    ink = colors.HexColor("#20312B")
    muted = colors.HexColor("#68766F")
    line = colors.HexColor("#DCE5DF")
    white = colors.white

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=19 * mm,
        title=f"Sylvan Watch - Analysis {run_id}",
        author="Sylvan Watch",
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=28,
        textColor=forest,
        alignment=TA_LEFT,
        spaceAfter=5,
    ))

    styles.add(ParagraphStyle(
        name="Subtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=14,
        textColor=muted,
        spaceAfter=12,
    ))

    styles.add(ParagraphStyle(
        name="Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=forest,
        spaceBefore=13,
        spaceAfter=7,
    ))

    styles.add(ParagraphStyle(
        name="BodySmall",
        parent=styles["BodyText"],
        fontSize=8.5,
        leading=12,
        textColor=ink,
    ))

    styles.add(ParagraphStyle(
        name="MutedSmall",
        parent=styles["BodyText"],
        fontSize=7.5,
        leading=10,
        textColor=muted,
    ))

    styles.add(ParagraphStyle(
        name="KpiValue",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=forest,
        alignment=TA_LEFT,
    ))

    styles.add(ParagraphStyle(
        name="KpiLabel",
        parent=styles["BodyText"],
        fontSize=7.5,
        leading=10,
        textColor=muted,
    ))

    styles.add(ParagraphStyle(
        name="TableHead",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=white,
    ))

    styles.add(ParagraphStyle(
        name="TableCell",
        parent=styles["BodyText"],
        fontSize=7.3,
        leading=9,
        textColor=ink,
    ))

    def para(value, style="BodySmall"):
        return Paragraph(escape(str(value)), styles[style])

    def section(title):
        return Paragraph(escape(title.upper()), styles["Section"])

    def footer(canvas, document):
        canvas.saveState()
        width, height = A4

        canvas.setStrokeColor(line)
        canvas.setLineWidth(0.5)
        canvas.line(
            18 * mm,
            14 * mm,
            width - 18 * mm,
            14 * mm,
        )

        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(muted)
        canvas.drawString(
            18 * mm,
            9 * mm,
            "SYLVAN WATCH  |  DEFORESTATION ANALYSIS",
        )
        canvas.drawRightString(
            width - 18 * mm,
            9 * mm,
            f"Page {document.page}",
        )

        canvas.restoreState()

    story = []

    story.append(Paragraph(
        "SYLVAN WATCH",
        ParagraphStyle(
            "Brand",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=forest,
            spaceAfter=10,
        ),
    ))

    story.append(HRFlowable(
        width="100%",
        thickness=2,
        color=accent,
        spaceAfter=13,
    ))

    story.append(Paragraph(
        "Forest Change<br/>Analysis Report",
        styles["ReportTitle"],
    ))

    story.append(Paragraph(
        f"Run ID: {escape(run_id)}  |  Generated from saved analysis results",
        styles["Subtitle"],
    ))

    # Analysis metadata
    bbox = request["bbox"]

    metadata = [
        [
            para("ANALYSIS PERIOD", "MutedSmall"),
            para("AREA BOUNDS (W, S, E, N)", "MutedSmall"),
            para("MODEL", "MutedSmall"),
        ],
        [
            para(f'{request["before_year"]} to {request["after_year"]}'),
            para(", ".join(f"{v:.5f}" for v in bbox)),
            para(model["name"]),
        ],
    ]

    meta_table = Table(
        metadata,
        colWidths=[43 * mm, 77 * mm, 50 * mm],
    )

    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), forest_light),
        ("BOX", (0, 0), (-1, -1), 0.5, line),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    story += [meta_table, Spacer(1, 12)]

    # Key findings
    story.append(section("Key findings"))

    kpis = [
        [
            para(f'{summary["loss_area_ha"]} ha', "KpiValue"),
            para(str(summary["detections"]), "KpiValue"),
            para(f'{quality["cloud_free_coverage_percent"]}%', "KpiValue"),
        ],
        [
            para("Estimated forest-cover loss", "KpiLabel"),
            para("Detected loss patches", "KpiLabel"),
            para("Cloud-free coverage", "KpiLabel"),
        ],
    ]

    kpi_table = Table(
        kpis,
        colWidths=[56.7 * mm] * 3,
        rowHeights=[13 * mm, 10 * mm],
    )

    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), forest_light),
        ("BOX", (0, 0), (-1, -1), 0.5, line),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, line),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story += [kpi_table, Spacer(1, 5)]

    story.append(para(
        f'Estimated loss is {summary["loss_percent_of_forest"]}% of '
        f'{summary["forest_area_ha"]} ha of scanned forest. '
        f'Decision threshold: {model.get("threshold", 0.5)}. '
        f'Season months: {request["season_months"][0]}-'
        f'{request["season_months"][1]}.'
    ))

    # Satellite imagery from this specific saved run
    if run_dir is not None:
        before_path = run_dir / "before.png"
        after_path = run_dir / "after.png"
        change_path = run_dir / "change.png"

        if before_path.is_file() and after_path.is_file():
            story.append(section("Satellite imagery"))

            before_img = PILImage.open(before_path).convert("RGB")
            after_img = PILImage.open(after_path).convert("RGB")

            def make_image_flowable(pil_img, max_width, max_height):
                """Create a correctly scaled ReportLab image."""
                width_px, height_px = pil_img.size

                scale = min(
                    max_width / width_px,
                    max_height / height_px,
                )

                image_buffer = BytesIO()
                pil_img.save(image_buffer, format="PNG")
                image_buffer.seek(0)

                return PDFImage(
                    image_buffer,
                    width=width_px * scale,
                    height=height_px * scale,
                )

            # Before and after images side by side
            panel_width = 82 * mm
            panel_height = 67 * mm

            before_pdf = make_image_flowable(
                before_img,
                panel_width,
                panel_height,
            )

            after_pdf = make_image_flowable(
                after_img,
                panel_width,
                panel_height,
            )

            image_table = Table(
                [
                    [before_pdf, after_pdf],
                    [
                        para(f'BEFORE — {request["before_year"]}', "MutedSmall"),
                        para(f'AFTER — {request["after_year"]}', "MutedSmall"),
                    ],
                ],
                colWidths=[87 * mm, 87 * mm],
            )

            image_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))

            story.append(image_table)

            # Composite the transparent change mask over the after image
            if change_path.is_file():
                overlay = PILImage.open(change_path).convert("RGBA")

                if overlay.size == after_img.size:
                    after_rgba = after_img.convert("RGBA")

                    combined = PILImage.alpha_composite(
                        after_rgba,
                        overlay,
                    ).convert("RGB")

                    story.append(Spacer(1, 7))
                    story.append(para(
                        "DETECTED CHANGE OVERLAY",
                        "MutedSmall",
                    ))

                    overlay_pdf = make_image_flowable(
                        combined,
                        174 * mm,
                        125 * mm,
                    )

                    story.append(overlay_pdf)
                else:
                    story.append(para(
                        "The saved change mask dimensions did not match "
                        "the after image. The overlay was omitted.",
                        "MutedSmall",
                    ))

            before_img.close()
            after_img.close()

    # Largest detected patches
    story.append(section("Largest detected patches"))

    table_data = [[
        para("#", "TableHead"),
        para("Longitude", "TableHead"),
        para("Latitude", "TableHead"),
        para("Area (ha)", "TableHead"),
        para("Confidence", "TableHead"),
        para("Land cover (2021)", "TableHead"),
    ]]

    for feature in detections.get("features", [])[:20]:
        p = feature["properties"]

        confidence = (
            "N/A"
            if p.get("confidence") is None
            else f'{p["confidence"]:.2f}'
        )

        table_data.append([
            para(p.get("id", ""), "TableCell"),
            para(f'{p["lon"]:.5f}', "TableCell"),
            para(f'{p["lat"]:.5f}', "TableCell"),
            para(p.get("area_ha", ""), "TableCell"),
            para(confidence, "TableCell"),
            para(p.get("landcover", "Unknown"), "TableCell"),
        ])

    if len(table_data) == 1:
        table_data.append([
            para("No detection patches recorded."),
            "", "", "", "", "",
        ])

    detection_table = Table(
        table_data,
        colWidths=[
            10 * mm,
            25 * mm,
            25 * mm,
            23 * mm,
            24 * mm,
            63 * mm,
        ],
        repeatRows=1,
    )

    detection_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), forest),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, forest_light]),
        ("GRID", (0, 0), (-1, -1), 0.35, line),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(detection_table)

    story.append(para(
        "Confidence values are model scores, not probabilities that "
        "an activity was illegal.",
        "MutedSmall",
    ))

    # Model evaluation
    story.append(section("Model evaluation"))

    if model.get("evaluated"):
        evaluation = (
            f'F1: {model["test_f1"]:.3f}  |  '
            f'Precision: {model["test_precision"]:.3f}  |  '
            f'Recall: {model["test_recall"]:.3f}  |  '
            f'IoU: {model["test_iou"]:.3f}'
        )

        story.append(para(evaluation))
        story.append(Spacer(1, 4))

        story.append(para(
            "These are held-out test metrics measured against Hansen "
            "reference labels, not field-verified ground truth. "
            f'Metrics generated: {model.get("metrics_generated_at", "not recorded")}.'
        ))
    else:
        story.append(para(
            "No evaluation was recorded for this model; accuracy is unknown."
        ))

    # Data sources
    story.append(section("Data sources"))

    for name, description in result.get("datasets", {}).items():
        story.append(KeepTogether([
            para(f"{name}: {description}"),
            Spacer(1, 3),
        ]))

    # Limitations
    story.append(section("Limitations and interpretation"))

    limitations = [*result.get("notes", []), *CAVEATS]

    for item in limitations:
        story.append(KeepTogether([
            Paragraph(
                "• " + escape(str(item)),
                styles["BodySmall"],
            ),
            Spacer(1, 3),
        ]))

    story.append(Spacer(1, 8))
    story.append(HRFlowable(
        width="100%",
        thickness=0.7,
        color=line,
    ))
    story.append(Spacer(1, 5))

    story.append(para(
        "This report identifies potential forest-cover change for further "
        "review. Satellite imagery alone cannot determine whether tree "
        "removal was legally authorized.",
        "MutedSmall",
    ))

    doc.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer,
    )

    return buffer.getvalue()
