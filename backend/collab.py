from fastapi import APIRouter, Depends, HTTPException,WebSocket
from auth import get_current_user
import secrets
from pymongo import MongoClient
import os
router = APIRouter(tags=["Collaboration"])

client = MongoClient(os.getenv('MONGO_URI'))


if not os.getenv("MONGO_URI"):
    raise Exception("MONGO_URI not set")


db = client["pasteDB"]
collab_collection = db["collaborations"]
pastes_collection = db["pastes"]
users_collection = db["users"]
api_keys_collection = db["api_keys"]
versions_collection = db["pasteVersions"]


@router.post("/collab/create/{paste_id}")
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


@router.get("/collab/{invite_token}")
async def get_collaboration(invite_token: str):
    collab = collab_collection.find_one(
        {"invite_token": invite_token},
        {"_id": 0}
    )

    if not collab:
        raise HTTPException(404, "Collaboration not found")

    return collab


HOSTS={}
@router.websocket("/collab/ws/{invite_token}")
async def collab_ws(websocket: WebSocket, invite_token: str):
    await websocket.accept()

    while True:
        data = await websocket.receive_json()
        
        if data["type"] == "connect" and data["role"] == "host":
            HOSTS[invite_token] = websocket

        if data["type"] == "join_request":

        host_ws = HOSTS.get(invite_token)

            if host_ws:
                await host_ws.send_json({
                    "type": "join_request",
                    "name": data["name"],
                    "role": data["role"]
                })

        # Handle:
        # join_request
        # approve
        # reject
        # edit
        # cursor
        # leave
