from fastapi import APIRouter, Response, HTTPException
from pydantic import BaseModel

from google.oauth2 import id_token
from google.auth.transport import requests

from jose import jwt

from datetime import datetime, timedelta, timezone

import os


router = APIRouter()


# ENV VARIABLES
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

SECRET_KEY = os.getenv("SECRET_KEY")

ALGORITHM = "HS256"


# REQUEST MODEL
class GoogleLogin(BaseModel):

    token: str


@router.post("/auth/google")
async def google_auth(
    data: GoogleLogin,
    response: Response
):

    try:

        # VERIFY GOOGLE TOKEN
        user_data = id_token.verify_oauth2_token(

            data.token,

            requests.Request(),

            GOOGLE_CLIENT_ID
        )

        # USER INFO
        email = user_data.get("email")

        name = user_data.get("name")

        picture = user_data.get("picture")


        # JWT PAYLOAD
        payload = {

            "email": email,

            "name": name,

            "picture": picture,

            "exp":
            datetime.now(
                timezone.utc
            ) + timedelta(days=7)

        }


        # CREATE JWT
        access_token = jwt.encode(

            payload,

            SECRET_KEY,

            algorithm=ALGORITHM
        )


        # SAVE COOKIE
        response.set_cookie(

            key="session",

            value=access_token,

            httponly=True,

            secure=True,

            samesite="none",

            max_age=60 * 60 * 24 * 7
        )


        return {

            "status": "success",

            "user": {

                "email": email,

                "name": name,

                "picture": picture
            }
        }


    except Exception as e:

        raise HTTPException(

            status_code=401,

            detail=str(e)
        )
