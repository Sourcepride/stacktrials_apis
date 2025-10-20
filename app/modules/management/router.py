from fastapi import APIRouter, BackgroundTasks, Body

from app.common.email_utils import send_email
from app.core.dependencies import SessionDep
from app.schemas.base import ContactForm, ContactFormResponse

router = APIRouter()


@router.post("/contact", response_model=ContactFormResponse)
async def contact(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    data: ContactForm = Body(ContactForm),
):
    await send_email(
        background_tasks,
        ["support@stacktrails.com"],
        "Customer Ticket",
        "feedback.html",
        {"title": data.title, "message": data.message},
    )
    return {"success": True, "message": "thanks for your feedback"}
