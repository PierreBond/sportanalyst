from __future__ import annotations

from io import BytesIO
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def export_markdown_to_pdf(markdown_content: str) -> bytes:
    """Convert a Markdown report to PDF bytes.

    Uses a simple HTML-to-PDF pipeline. In production, this would use
    weasyprint or a similar library.

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
