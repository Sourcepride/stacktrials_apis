from app.models.user_model import Account
from app.schemas.account import ProfileUpdate


async def get_profile(username: str):
    pass


async def update_current_profile(
    username: str, current_user: Account, data: ProfileUpdate
):
    pass
