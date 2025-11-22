from app.models.notification_model import NotificationBase


class NotificationRead(NotificationBase):
    id: str
    account_id: str


class NotificationWrite(NotificationBase):
    pass
