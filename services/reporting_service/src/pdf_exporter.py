from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import structlog

from .report_builder import MatchResearchSnapshot, build_html_report, build_markdown_report

logger = structlog.get_logger(__name__)


def export_markdown_to_pdf(markdown_content: str) -> bytes:
    """Convert a Markdown report to PDF bytes.

    Args:
        markdown_content: The Markdown string to convert.

    Returns:
        PDF file content as bytes.

    Raises:
        ImportError: If required PDF generation libraries are not installed.
    """
    try:
        import markdown
        from weasyprint import HTML
    except ImportError:
        logger.warning("pdf_export_dependencies_missing")
        raise ImportError(
            "PDF export requires 'markdown' and 'weasyprint' packages. "
            "Install with: pip install markdown weasyprint"
        )

    html_content = markdown.markdown(markdown_content, extensions=["tables"])

    styled_html = f"""<!DOCTYPE html>
<html>
<head>
<style>
    body {{ font-family: Arial, sans-serif; margin: 40px; }}
    h1 {{ color: #1a1a2e; }}
    h2 {{ color: #16213e; }}
    h3 {{ color: #0f3460; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background-color: #0f3460; color: white; }}
    hr {{ border: 1px solid #ddd; margin: 32px 0; }}
</style>
</head>
<body>
{html_content}
</body>
</html>"""

    pdf_bytes = HTML(string=styled_html).write_pdf()
    logger.info("pdf_exported", size_bytes=len(pdf_bytes))
    return pdf_bytes


def export_html_to_pdf(html_content: str) -> bytes:
    """Convert an HTML report to PDF bytes.

    Args:
        html_content: The HTML string to convert.

    Returns:
        PDF file content as bytes.

    Raises:
        ImportError: If required PDF generation libraries are not installed.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        logger.warning("pdf_export_dependencies_missing")
        raise ImportError(
            "PDF export requires 'weasyprint' package. Install with: pip install weasyprint"
        )

    pdf_bytes = HTML(string=html_content).write_pdf()
    logger.info("pdf_exported", size_bytes=len(pdf_bytes))
    return pdf_bytes


def generate_pdf_report(snapshot: MatchResearchSnapshot) -> bytes:
    """Generate a complete PDF report from a snapshot.

    Args:
        snapshot: The assembled match research data.

    Returns:
        PDF file content as bytes.
    """
    html_content = build_html_report(snapshot)
    return export_html_to_pdf(html_content)


def generate_markdown_report(snapshot: MatchResearchSnapshot) -> str:
    """Generate a complete Markdown report from a snapshot.

    Args:
        snapshot: The assembled match research data.

    Returns:
        Markdown string of the full report.
    """
    return build_markdown_report(snapshot)
