from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from auth import get_current_user
import secrets
from pymongo import MongoClient
import os
from uuid import uuid4
import base64
import json

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


async def broadcast_members(invite_token):
    collab = collab_collection.find_one({
        "invite_token": invite_token
    })

    if not collab:
        return

    members = collab.get("members", [])

    # Send to host
    host_ws = HOSTS.get(invite_token)

    if host_ws:
        try:
            await host_ws.send_json({
                "type": "participants",
                "users": members
            })
        except Exception as e:
            print("Failed to send members to host:", e)

    # Send to approved guests
    guests = GUESTS.get(invite_token, {})

    for gid, guest in list(guests.items()):

        if not guest.get("approved", False):
            continue

        try:
            await guest["websocket"].send_json({
                "type": "participants",
                "users": members
            })
        except Exception as e:
            print(
                "Failed to send members to guest:",
                gid,
                e
            )


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


def encode_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def decode_bytes(data: str) -> bytes:
    return base64.b64decode(data)



@router.websocket("/collab/ws/{invite_token}")
async def collab_ws(
    websocket: WebSocket,
    invite_token: str
):
    await websocket.accept()

    guest_id = None
    role = None

    try:
        while True:

            data = await websocket.receive_json()
            message_type = data.get("type")

            # =====================================================
            # CONNECT
            # =====================================================

            if message_type == "connect":

                role = data.get("role")

                # =================================================
                # HOST
                # =================================================

                if role == "host":

                    HOSTS[invite_token] = websocket

                    print(
                        "Host connected:",
                        invite_token
                    )

                    # ---------------------------------------------
                    # Get host name from users collection
                    # ---------------------------------------------

                    collab = collab_collection.find_one({
                        "invite_token": invite_token
                    })

                    host_name = "Host"

                    if collab:

                        host_email = collab.get("owner")

                        host_user = users_collection.find_one({
                            "email": host_email
                        })

                        if host_user:

                            host_name = (
                                host_user.get("name")
                                or host_user.get(
                                    "email",
                                    "Host"
                                ).split("@")[0]
                            )

                        # -----------------------------------------
                        # Add host to members if not already there
                        # -----------------------------------------

                        members = collab.get(
                            "members",
                            []
                        )

                        host_exists = any(
                            member.get("guest_id") == "host"
                            for member in members
                        )

                        if not host_exists:

                            collab_collection.update_one(
                                {
                                    "invite_token": invite_token
                                },
                                {
                                    "$push": {
                                        "members": {
                                            "guest_id": "host",
                                            "name": host_name,
                                            "role": "host"
                                        }
                                    }
                                }
                            )

                    # Tell host connection succeeded

                    await websocket.send_json({
                        "type": "connected",
                        "role": "host"
                    })

                    # Send participant list

                    await broadcast_members(
                        invite_token
                    )

                # =================================================
                # GUEST
                # =================================================

                else:

                    guest_id = str(uuid4())

                    GUESTS.setdefault(
                        invite_token,
                        {}
                    )

                    GUESTS[invite_token][guest_id] = {

                        "websocket": websocket,

                        "name": data.get(
                            "name",
                            "Guest"
                        ),

                        "role": data.get(
                            "role",
                            "viewer"
                        ),

                        "approved": False
                    }

                    print(
                        "Guest connected:",
                        guest_id,
                        data.get("name")
                    )

                    await websocket.send_json({
                        "type": "connected",
                        "role": role,
                        "guest_id": guest_id
                    })

            # =====================================================
            # REQUEST FULL SYNC
            # =====================================================

            elif message_type == "request_sync":

                # Guests request the current YJS state
                if role == "host":
                    continue

                host_ws = HOSTS.get(
                    invite_token
                )

                if host_ws:

                    await host_ws.send_json({
                        "type": "sync_request",
                        "guest_id": guest_id
                    })

            # =====================================================
            # JOIN REQUEST
            # =====================================================

            elif message_type == "join_request":

                host_ws = HOSTS.get(
                    invite_token
                )

                if not host_ws or not guest_id:
                    continue

                guest = GUESTS.get(
                    invite_token,
                    {}
                ).get(guest_id)

                if not guest:
                    continue

                # ---------------------------------------------
                # Get name and requested role
                # ---------------------------------------------

                name = (
                    data.get("name")
                    or ""
                ).strip()

                requested_role = (
                    data.get("role")
                    or guest.get("role")
                    or "viewer"
                )

                if not name:
                    name = "Guest"

                # Only allow valid roles

                if requested_role not in (
                    "viewer",
                    "editor"
                ):
                    requested_role = "viewer"

                # Update temporary guest information

                guest["name"] = name
                guest["role"] = requested_role

                print(
                    "Join request:",
                    name,
                    requested_role,
                    guest_id
                )

                # Send request to host

                await host_ws.send_json({
                    "type": "join_request",
                    "guest_id": guest_id,
                    "name": name,
                    "role": requested_role
                })

            # =====================================================
            # APPROVE GUEST
            # =====================================================

            elif message_type == "join_approved":

                # Only host can approve

                if role != "host":
                    continue

                target_guest_id = data.get(
                    "guest_id"
                )

                guest = GUESTS.get(
                    invite_token,
                    {}
                ).get(target_guest_id)

                if not guest:
                    continue

                collab = collab_collection.find_one({
                    "invite_token": invite_token
                })

                if not collab:
                    continue

                custom_id = collab["paste_id"]

                # Mark guest approved

                guest["approved"] = True

                # ---------------------------------------------
                # Create member record
                # ---------------------------------------------

                member = {
                    "guest_id": target_guest_id,
                    "name": guest.get(
                        "name",
                        "Guest"
                    ),
                    "role": guest.get(
                        "role",
                        "viewer"
                    )
                }

                # ---------------------------------------------
                # Remove duplicate member if it exists
                # ---------------------------------------------

                collab_collection.update_one(
                    {
                        "invite_token": invite_token
                    },
                    {
                        "$pull": {
                            "members": {
                                "guest_id": target_guest_id
                            }
                        }
                    }
                )

                # ---------------------------------------------
                # Store approved member in MongoDB
                # ---------------------------------------------

                collab_collection.update_one(
                    {
                        "invite_token": invite_token
                    },
                    {
                        "$push": {
                            "members": member
                        }
                    }
                )

                # ---------------------------------------------
                # Tell guest they were approved
                # ---------------------------------------------

                await guest["websocket"].send_json({
                    "type": "join_approved",
                    "guest_id": target_guest_id,
                    "role": guest["role"],
                    "custom_id": custom_id
                })

                print(
                    "Guest approved:",
                    target_guest_id,
                    member
                )

                # ---------------------------------------------
                # Send updated member list to everyone
                # ---------------------------------------------

                await broadcast_members(
                    invite_token
                )

            # =====================================================
            # REJECT GUEST
            # =====================================================

            elif message_type == "join_rejected":

                # Only host can reject

                if role != "host":
                    continue

                target_guest_id = data.get(
                    "guest_id"
                )

                guest = GUESTS.get(
                    invite_token,
                    {}
                ).get(target_guest_id)

                if guest:

                    await guest["websocket"].send_json({
                        "type": "join_rejected"
                    })

            # =====================================================
            # FULL YJS STATE
            # =====================================================

            elif message_type == "yjs_full_state":

                if role != "host":
                    continue

                encoded_state = data.get(
                    "update"
                )

                target_guest_id = data.get(
                    "guest_id"
                )

                if not encoded_state:
                    continue

                if not target_guest_id:
                    continue

                guest = GUESTS.get(
                    invite_token,
                    {}
                ).get(target_guest_id)

                if not guest:
                    continue

                # Guest must be approved

                if not guest.get(
                    "approved",
                    False
                ):
                    continue

                try:

                    await guest["websocket"].send_json({
                        "type": "yjs_full_state",
                        "update": encoded_state
                    })

                except Exception as e:

                    print(
                        "Failed full sync:",
                        target_guest_id,
                        e
                    )

            # =====================================================
            # YJS INCREMENTAL UPDATE
            # =====================================================

            elif message_type == "yjs_update":

                encoded_update = data.get(
                    "update"
                )

                if not encoded_update:
                    continue

                # =================================================
                # PERMISSION CHECK
                # =================================================

                if role == "host":

                    # Host can edit

                    pass

                else:

                    guest = GUESTS.get(
                        invite_token,
                        {}
                    ).get(guest_id)

                    if not guest:

                        await websocket.send_json({
                            "type": "error",
                            "message": "Guest not found."
                        })

                        continue

                    # Guest must be approved

                    if not guest.get(
                        "approved",
                        False
                    ):

                        await websocket.send_json({
                            "type": "error",
                            "message": "You are not approved."
                        })

                        continue

                    # Viewer cannot edit

                    if guest.get("role") == "viewer":

                        await websocket.send_json({
                            "type": "error",
                            "message": "Viewers cannot edit."
                        })

                        continue

                # =================================================
                # VALIDATE BASE64
                # =================================================

                try:

                    decode_bytes(
                        encoded_update
                    )

                except Exception:

                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid Yjs update."
                    })

                    continue

                # =================================================
                # SEND UPDATE TO HOST
                # =================================================

                host_ws = HOSTS.get(
                    invite_token
                )

                if (
                    host_ws
                    and host_ws != websocket
                ):

                    try:

                        await host_ws.send_json({
                            "type": "yjs_update",
                            "update": encoded_update
                        })

                    except Exception as e:

                        print(
                            "Failed to send update to host:",
                            e
                        )

                # =================================================
                # SEND UPDATE TO OTHER APPROVED GUESTS
                # =================================================

                guests = GUESTS.get(
                    invite_token,
                    {}
                )

                for gid, guest in list(
                    guests.items()
                ):

                    guest_ws = guest.get(
                        "websocket"
                    )

                    if not guest_ws:
                        continue

                    # Don't send back to sender

                    if guest_ws == websocket:
                        continue

                    # Only approved guests receive updates

                    if not guest.get(
                        "approved",
                        False
                    ):
                        continue

                    try:

                        await guest_ws.send_json({
                            "type": "yjs_update",
                            "update": encoded_update
                        })

                    except Exception as e:

                        print(
                            "Failed to send update to guest:",
                            gid,
                            e
                        )

    # =============================================================
    # DISCONNECT
    # =============================================================

    except WebSocketDisconnect:

        print(
            "WebSocket disconnected:",
            invite_token,
            guest_id
        )

    except Exception as e:

        print(
            "WebSocket error:",
            invite_token,
            guest_id,
            e
        )

    finally:

        # =========================================================
        # REMOVE HOST CONNECTION
        # =========================================================

        if HOSTS.get(
            invite_token
        ) == websocket:

            del HOSTS[
                invite_token
            ]

        # =========================================================
        # REMOVE GUEST CONNECTION
        # =========================================================

        if guest_id:

            guests = GUESTS.get(
                invite_token,
                {}
            )

            guests.pop(
                guest_id,
                None
            )

            if not guests:

                GUESTS.pop(
                    invite_token,
                    None
							)
