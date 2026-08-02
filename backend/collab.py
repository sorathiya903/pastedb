from fastapi import APIRouter, Depends, HTTPException
from auth import get_current_user
import secrets
from pymongo import MongoClient

router = APIRouter(prefix="/collab", tags=["Collaboration"])

client = MongoClient(os.getenv('MONGO_URI'))


if not os.getenv("MONGO_URI"):
    raise Exception("MONGO_URI not set")


db = client["pasteDB"]
collab_collection = db["collaborations"]

@router.post("/create/{paste_id}")
async def create_collaboration(
    paste_id: str,
    user=Depends(get_current_user)
):
    email_key = user["email"].replace(".", "_")

    paste = pastes_collection.find_one({
        "custom_id": paste_id
    })

    if not paste:
        raise HTTPException(404, "Paste not found")

    if paste.get("user_email_key") != email_key:
        raise HTTPException(403, "Unauthorized")

    existing = collab_collection.find_one({
        "paste_id": paste_id
    })

    if existing:
        return {
            "success": True,
            "invite_token": existing["invite_token"]
        }

    token = secrets.token_urlsafe(24)

    collab_collection.insert_one({
        "paste_id": paste_id,
        "owner": user["email"],
        "invite_token": token,
        "pending": [],
        "members": []
    })

    return {
        "success": True,
        "invite_token": token
    }
