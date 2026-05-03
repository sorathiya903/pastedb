from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import pymongo


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace "*" with your frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)


class DATA(BaseModel):
    name: str
    age: int

@app.get("/")
def home():
    return {"message": "Server running"}


@app.get("/create")
def create():
    return {"res": "This create endpoint is working!!"}


@app.post("/test")
async def test(data: DATA):
    name = data.name
    age= data.age
    res = f"the user name is  {name} and the age is {age}."
    return {"ans":res}
    
