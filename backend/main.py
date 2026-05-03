from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient

client = MongoClient("mongodb://Aditya:Qu1IZrvVdB0ajaCm@ac-zqtl0lb-shard-00-00.fz0oqsr.mongodb.net:27017,ac-zqtl0lb-shard-00-01.fz0oqsr.mongodb.net:27017,ac-zqtl0lb-shard-00-02.fz0oqsr.mongodb.net:27017/?ssl=true&replicaSet=atlas-10lbo4-shard-0&authSource=admin&appName=Cluster0")
db = client["pasteDB"]
collection = db["pastes"]

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


@app.post('/add')
async def add(data:DATA):
    user={
        "name":data.name,
        'age':data.age

    }
    collection.insert_one(user)
    return {"r":f'Added {data.name} with age {data.age}.'}
                                            
    
