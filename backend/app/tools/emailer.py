"""Simulated email sender — prints the email envelope and saves it to disk."""

from datetime import UTC, datetime
from pathlib import Path

from langchain_core.tools import tool

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"


def send_newsletter_email(subject: str, body: str, output_format: str = "markdown") -> str:
    """Simulate sending the newsletter to subscribers: print the email
    (To/Subject/Body) and save it to a file. Returns the saved file path."""
    to = "subscribers@newsletter.example"
    envelope = (
        f"From: Newsletter Agent <agent@newsletter.example>\n"
        f"To: {to}\n"
        f"Subject: {subject}\n"
        f"Date: {datetime.now(UTC):%a, %d %b %Y %H:%M:%S %z}\n"
        f"{'-' * 60}\n"
        f"{body}\n"
    )
    print("\n===== SIMULATED EMAIL SEND =====")
    print(envelope)

    OUTPUT_DIR.mkdir(exist_ok=True)
    suffix = ".html" if output_format == "html" else ".md"
    path = OUTPUT_DIR / f"newsletter{suffix}"
    path.write_text(body, encoding="utf-8")
    return str(path)


send_newsletter_email_tool = tool(send_newsletter_email)
