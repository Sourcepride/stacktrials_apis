import datetime
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

load_dotenv()

cnf = lambda: Path(__file__).parent.parent / "templates"

# === CONFIGURATION ===
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", "support@stackdrills.com"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", "your_app_password_here"),
    MAIL_FROM=os.getenv("MAIL_FROM", "support@stackdrills.com"),
    MAIL_PORT=587,
    MAIL_SERVER=os.getenv("SMTP_HOST", "smtp.zoho.com"),
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER=Path(__file__).parent.parent / "templates",
)


async def send_email(
    background_tasks: BackgroundTasks,
    recipients: list[str],
    subject: str,
    template_name: str,
    context: dict,
):
    """
    Sends an email asynchronously using FastAPI-Mail and Jinja2 templates.
    """

    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        template_body={
            **context,
            "subject": subject,
            "current_year": datetime.datetime.now().year,
        },
        subtype=MessageType.html,
    )

    fm = FastMail(conf)
    background_tasks.add_task(fm.send_message, message, template_name=template_name)
