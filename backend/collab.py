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


async def broadcast_presence(invite_token):

    room_presence = PRESENCE.get(
        invite_token,
        {}
    )

    message = {
        "type": "presence_state",
        "users": room_presence
    }

    host_ws = HOSTS.get(invite_token)

    if host_ws:

        try:
            await host_ws.send_json(message)
        except Exception as e:
            print("Presence host error:", e)

    guests = GUESTS.get(
        invite_token,
        {}
    )

    for gid, guest in list(guests.items()):

        if not guest.get("approved", False):
            continue

        guest_ws = guest.get("websocket")

        if not guest_ws:
            continue

        try:
            await guest_ws.send_json(message)
        except Exception as e:
            print(
                "Presence guest error:",
                gid,
                e
			)



async def handle_presence(
    websocket,
    invite_token,
    guest_id,
    role,
    data
):
    presence = data.get("presence")

    if not presence:
        return

    participant_id = (
        "host"
        if role == "host"
        else guest_id
    )

    if role != "host":

        guest = (
            GUESTS
            .get(invite_token, {})
            .get(guest_id)
        )

        if not guest:
            return

        if not guest.get("approved", False):
            return

    PRESENCE.setdefault(
        invite_token,
        {}
    )[participant_id] = presence

    await broadcast_presence(
        invite_token
	)


		
async def broadcast_members(invite_token):

    collab = collab_collection.find_one({
        "invite_token": invite_token
    })

    if not collab:
        return

    members = collab.get("members", [])

    message = {
        "type": "participants",
        "users": members
    }

    # -----------------------------
    # HOST
    # -----------------------------

    host_ws = HOSTS.get(invite_token)

    if host_ws:

        try:

            await host_ws.send_json(message)

        except Exception as e:

            print(
                "Failed to send members to host:",
                e
            )

    # -----------------------------
    # GUESTS
    # -----------------------------

    guests = GUESTS.get(
        invite_token,
        {}
    )

    for gid, guest in list(
        guests.items()
    ):

        if not guest.get(
            "approved",
            False
        ):
            continue

        try:

            await guest["websocket"].send_json(
                message
            )

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
PRESENCE = {}

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
                # HOST CONNECT
                # =================================================

                if role == "host":

                    HOSTS[invite_token] = websocket

                    print(
                        "Host connected:",
                        invite_token
                    )

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
                        # Check if host already exists
                        # -----------------------------------------

                        members = collab.get(
                            "members",
                            []
                        )

                        host_exists = any(
                            member.get("guest_id") == "host"
                            for member in members
                        )

                        # -----------------------------------------
                        # Add host
                        # -----------------------------------------

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

                    await websocket.send_json({
                        "type": "connected",
                        "role": "host"
                    })

                    # Send participant list to everyone
                    await broadcast_members(
                        invite_token
                    )

                # =================================================
                # GUEST CONNECT
                # =================================================

                else:

                    guest_id = str(uuid4())

                    GUESTS.setdefault(
                        invite_token,
                        {}
                    )

                    GUESTS[invite_token][guest_id] = {

                        "websocket": websocket,

                        "name": (
                            data.get("name")
                            or "Guest"
                        ),

                        "role": (
                            data.get("role")
                            or "viewer"
                        ),

                        "approved": False
                    }

                    print(
                        "Guest connected:",
                        guest_id,
                        GUESTS[invite_token][guest_id]["name"]
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

                # -----------------------------------------
                # Get guest information
                # -----------------------------------------

                name = (
                    data.get("name")
                    or guest.get("name")
                    or "Guest"
                ).strip()

                requested_role = (
                    data.get("role")
                    or guest.get("role")
                    or "viewer"
                )

                # Only allow valid roles
                if requested_role not in (
                    "viewer",
                    "editor"
                ):
                    requested_role = "viewer"

                guest["name"] = name
                guest["role"] = requested_role

                print(
                    "Join request:",
                    guest_id,
                    name,
                    requested_role
                )

                await host_ws.send_json({

                    "type": "join_request",

                    "guest_id": guest_id,

                    "name": name,

                    "role": requested_role
                })

            # =====================================================
            # JOIN APPROVED
            # =====================================================
            elif message_type == "presence":
                await handle_presence(    websocket,   invite_token,    guest_id,    role,     data		)
           
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

                custom_id = collab.get(
                    "paste_id"
                )

                # -----------------------------------------
                # Mark approved
                # -----------------------------------------

                guest["approved"] = True

                member = {

                    "guest_id": target_guest_id,

                    "name": (
                        guest.get("name")
                        or "Guest"
                    ),

                    "role": (
                        guest.get("role")
                        or "viewer"
                    )
                }

                # -----------------------------------------
                # Remove old entry if it exists
                # -----------------------------------------

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

                # -----------------------------------------
                # Add approved member
                # -----------------------------------------

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

                # -----------------------------------------
                # Tell guest
                # -----------------------------------------

                await guest["websocket"].send_json({

                    "type": "join_approved",

                    "guest_id": target_guest_id,

                    "role": guest["role"],

                    "custom_id": custom_id
                })

                print(
                    "Guest approved:",
                    member
                )

                # -----------------------------------------
                # Broadcast updated list
                # -----------------------------------------

                await broadcast_members(
                    invite_token
                )

            # =====================================================
            # JOIN REJECTED
            # =====================================================

            elif message_type == "join_rejected":

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

                if not encoded_state or not target_guest_id:
                    continue

                guest = GUESTS.get(
                    invite_token,
                    {}
                ).get(target_guest_id)

                if not guest:
                    continue

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
            # YJS UPDATE
            # =====================================================

            elif message_type == "yjs_update":

                encoded_update = data.get(
                    "update"
                )

                if not encoded_update:
                    continue

                # -----------------------------------------
                # HOST
                # -----------------------------------------

                if role == "host":

                    pass

                # -----------------------------------------
                # GUEST
                # -----------------------------------------

                else:

                    guest = GUESTS.get(
                        invite_token,
                        {}
                    ).get(guest_id)

                    if not guest:

                        await websocket.send_json({

                            "type": "error",

                            "message":
                                "Guest not found."
                        })

                        continue

                    # Must be approved
                    if not guest.get(
                        "approved",
                        False
                    ):

                        await websocket.send_json({

                            "type": "error",

                            "message":
                                "You are not approved."
                        })

                        continue

                    # Viewer cannot edit
                    if guest.get(
                        "role"
                    ) == "viewer":

                        await websocket.send_json({

                            "type": "error",

                            "message":
                                "Viewers cannot edit."
                        })

                        continue

                # -----------------------------------------
                # Validate Yjs update
                # -----------------------------------------

                try:

                    decode_bytes(
                        encoded_update
                    )

                except Exception:

                    await websocket.send_json({

                        "type": "error",

                        "message":
                            "Invalid Yjs update."
                    })

                    continue

                # -----------------------------------------
                # Send to host
                # -----------------------------------------

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

                # -----------------------------------------
                # Send to other approved guests
                # -----------------------------------------

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

                    # Don't send to sender
                    if guest_ws == websocket:
                        continue

                    # Only approved guests
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
            guest_id,
            role
        )

    except Exception as e:

        print(
            "WebSocket error:",
            invite_token,
            guest_id,
            role,
            e
        )

    finally:

        # =========================================================
        # HOST DISCONNECTED
        # =========================================================

        if role == "host":

            # Only remove if this exact websocket is the host
            if HOSTS.get(
                invite_token
            ) == websocket:

                HOSTS.pop(
                    invite_token,
                    None
                )

            # Remove host from database
            collab_collection.update_one(
                {
                    "invite_token": invite_token
                },
                {
                    "$pull": {
                        "members": {
                            "guest_id": "host"
                        }
                    }
                }
            )

            print(
                "Host removed from members:",
                invite_token
            )

            # Broadcast updated list
            await broadcast_members(
                invite_token
            )

        # =========================================================
        # GUEST DISCONNECTED
        # =========================================================
            elif guest_id:
			
			    # =========================================================
			    # GUEST DISCONNECTED
			    # =========================================================
			
			    guests = GUESTS.get(
			        invite_token,
			        {}
			    )
			
			    guest = guests.get(guest_id)
			
			    # ---------------------------------------------------------
			    # Remove guest from GUESTS
			    # ---------------------------------------------------------
			
			    if guest:
			
			        # Important: only remove if this websocket
			        # actually belongs to this guest
			        if guest.get("websocket") == websocket:
			
			            guests.pop(
			                guest_id,
			                None
			            )
			
			            print(
			                "Guest removed from GUESTS:",
			                guest_id
			            )
			
			    if not guests:
			
			        GUESTS.pop(
			            invite_token,
			            None
			        )
			
			    # ---------------------------------------------------------
			    # Remove guest cursor / presence
			    # ---------------------------------------------------------
			
			    room_presence = PRESENCE.get(
			        invite_token
			    )
			
			    if room_presence:
			
			        removed_presence = room_presence.pop(
			            guest_id,
			            None
			        )
			
			        if removed_presence:
			
			            print(
			                "Guest cursor removed:",
			                guest_id
			            )
			
			        # Remove empty room presence
			        if not room_presence:
			
			            PRESENCE.pop(
			                invite_token,
			                None
			            )
			
			    # ---------------------------------------------------------
			    # Remove guest from MongoDB members
			    # ---------------------------------------------------------
			
			    collab_collection.update_one(
			        {
			            "invite_token": invite_token
			        },
			        {
			            "$pull": {
			                "members": {
			                    "guest_id": guest_id
			                }
			            }
			        }
			    )
			
			    print(
			        "Guest removed from members:",
			        guest_id
			    )
			
			    # ---------------------------------------------------------
			    # Tell everyone that the cursor disappeared
			    # ---------------------------------------------------------
			
			    await broadcast_presence(
			        invite_token
			    )



            else:
				print("lastelse")
