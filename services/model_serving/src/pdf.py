"""Render a match research report as a PDF.

The report is the model's view of a fixture: outcome probabilities, expected
goals and the features that drive the prediction. It carries no prices -- the
value-bets board is the model-versus-market comparison, and this document
deliberately does not blur the two.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#111827")
MUTE = colors.HexColor("#6b7280")
RULE = colors.HexColor("#e5e7eb")
ACCENT = colors.HexColor("#4338ca")

DISCLAIMER = (
    "Model probabilities, not an edge signal. The value-bets board compares this "
    "model with the market; on the measured history the model loses to the market "
    "inside every edge bucket, so these numbers are not betting advice."
)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "meta": ParagraphStyle(
            "ReportMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=MUTE,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "ReportSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=ACCENT,
            spaceBefore=12,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=INK,
        ),
        "muted": ParagraphStyle(
            "ReportMuted",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=MUTE,
        ),
    }


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "-"


def _outcome_rows(report: dict[str, Any]) -> list[list[str]]:
    probs = report.get("probabilities") or {}
    teams = [report.get("home_team", "Home"), "Draw", report.get("away_team", "Away")]
    keys = ["home_win", "draw", "away_win"]
    rows: list[list[str]] = [["Outcome", "Probability"]]
    for label, key in zip(teams, keys):
        rows.append([str(label), _pct(probs.get(key))])
    return rows


def _driver_lines(report: dict[str, Any]) -> list[str]:
    shap = report.get("shap_explanation") or {}
    lines: list[str] = []
    for title, key in (("Pushing the home win up", "positive_drivers"),
                       ("Pushing it down", "negative_drivers")):
        drivers = shap.get(key) or []
        if not drivers:
            continue
        lines.append(f"<b>{title}</b>")
        for driver in drivers[:5]:
            label = driver.get("label") or driver.get("feature", "")
            impact = driver.get("impact")
            try:
                impact_text = f"{float(impact):+.3f}"
            except (TypeError, ValueError):
                impact_text = "-"
            lines.append(f"&bull; {label} ({impact_text})")
        lines.append("")
    return lines


def render_match_report_pdf(
    report: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    xg: dict[str, float] | None = None,
) -> bytes:
    """Render the report payload as a one-page PDF.

    Args:
        report: The prediction payload (teams, probabilities, shap drivers).
        metadata: Model metadata, used for the version and held-out metrics.
        xg: Expected goals for each side, when the goal model is available.

    Returns:
        The PDF document as bytes.
    """
    meta = metadata or {}
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Match report - {report.get('home_team', '')} vs {report.get('away_team', '')}",
        author="sportanalyst",
        pageCompression=0,
    )

    story: list[Any] = []
    home = str(report.get("home_team", "Home"))
    away = str(report.get("away_team", "Away"))
    story.append(Paragraph(f"{home} vs {away}", styles["title"]))

    scheduled = str(report.get("scheduled_at", ""))
    league = str(report.get("league", "")).replace("_", " ")
    generated = str(report.get("generated_at", ""))
    story.append(
        Paragraph(
            f"{league} &nbsp;&middot;&nbsp; kickoff {scheduled} &nbsp;&middot;&nbsp; "
            f"generated {generated}",
            styles["meta"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=2))

    version = meta.get("model_version") or report.get("model_version") or "unknown"
    accuracy = meta.get("accuracy")
    brier = meta.get("brier_score")
    base_rate = meta.get("accuracy_base_rate")
    metrics = [f"model {version}"]
    if accuracy is not None:
        metrics.append(f"held-out accuracy {_pct(accuracy)}")
    if brier is not None:
        metrics.append(f"Brier {float(brier):.4f}")
    if base_rate is not None:
        metrics.append(f"base rate {_pct(base_rate)}")
    story.append(Paragraph(" &nbsp;&middot;&nbsp; ".join(metrics), styles["muted"]))

    story.append(Paragraph("Outcome probabilities", styles["section"]))
    table = Table(_outcome_rows(report), colWidths=[95 * mm, 40 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TEXTCOLOR", (0, 0), (-1, 0), MUTE),
                ("TEXTCOLOR", (0, 1), (-1, -1), INK),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
            ]
        )
    )
    story.append(table)

    if xg:
        story.append(Paragraph("Expected goals", styles["section"]))
        try:
            story.append(
                Paragraph(
                    f"{home} {float(xg.get('home', 0)):.2f} &nbsp;&middot;&nbsp; "
                    f"{away} {float(xg.get('away', 0)):.2f} &nbsp;&middot;&nbsp; "
                    f"total {float(xg.get('total', 0)):.2f} goals",
                    styles["body"],
                )
            )
        except (TypeError, ValueError):
            pass

    driver_lines = _driver_lines(report)
    if driver_lines:
        story.append(Paragraph("What drives the model", styles["section"]))
        story.append(Paragraph("<br/>".join(driver_lines), styles["body"]))

    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=4))
    story.append(Paragraph(DISCLAIMER, styles["muted"]))

    # pageCompression=0 keeps the document greppable, which is what the test
    # asserts on; a one-page report is small enough that it costs nothing.
    doc.build(story)
    return buffer.getvalue()
