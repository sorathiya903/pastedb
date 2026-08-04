from fastapi import APIRouter, Depends, HTTPException,WebSocket
from auth import get_current_user
import secrets
from pymongo import MongoClient
import os
from uuid import uuid4
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




HOSTS = {}
GUESTS = {}


@router.websocket("/collab/ws/{invite_token}")
async def collab_ws(websocket: WebSocket, invite_token: str):

    await websocket.accept()

    guest_id = None

    try:

        while True:

            data = await websocket.receive_json()

            # =========================
            # CONNECT
            # =========================

            if data["type"] == "connect":

                role = data.get("role")

                # -------------------------
                # HOST
                # -------------------------

                if role == "host":

                    HOSTS[invite_token] = websocket

                    print("Host connected:", invite_token)

                    await websocket.send_json({
                        "type": "connected",
                        "role": "host"
                    })

                # -------------------------
                # GUEST
            # -------------------------

                else:

                    # Generate ID ONLY on backend
                    guest_id = str(uuid4())

                    GUESTS.setdefault(invite_token, {})

                    GUESTS[invite_token][guest_id] = {
                        "websocket": websocket,
                        "name": data.get("name", "Guest"),
                        "role": role
                    }

                    print(
                        "Guest connected:",
                        guest_id,
                        data.get("name")
                    )

                    # Send ID back to guest
                    await websocket.send_json({
                        "type": "connected",
                        "role": role,
                        "guest_id": guest_id
                    })


            # =========================
            # JOIN REQUEST
            # =========================

            elif data["type"] == "join_request":

                host_ws = HOSTS.get(invite_token)

                if host_ws and guest_id:

                    guest = GUESTS.get(
                        invite_token, {}
                    ).get(guest_id)

                    if guest:

                        await host_ws.send_json({
                            "type": "join_request",
                            "guest_id": guest_id,
                            "name": guest["name"],
                            "role": guest["role"]
                        })


            # =========================
            # APPROVE
            # =========================

            elif data["type"] == "join_approved":

                target_guest_id = data.get("guest_id")

                guest = GUESTS.get(
                    invite_token, {}
                ).get(target_guest_id)

                if guest:

                    await guest["websocket"].send_json({
                        "type": "join_approved"
                    })


            # =========================
            # REJECT
            # =========================

            elif data["type"] == "join_rejected":

                target_guest_id = data.get("guest_id")

                guest = GUESTS.get(
                    invite_token, {}
                ).get(target_guest_id)

                if guest:

                    await guest["websocket"].send_json({
                        "type": "join_rejected"
                    })


    except Exception as e:

        print("WebSocket disconnected:", e)

        # -------------------------
        # Remove host
        # -------------------------

        if HOSTS.get(invite_token) == websocket:
            del HOSTS[invite_token]

        # -------------------------
        # Remove guest
        # -------------------------

        if guest_id:

            guests = GUESTS.get(invite_token, {})

            guests.pop(guest_id, None)

            if not guests:
                GUESTS.pop(invite_token, None)
