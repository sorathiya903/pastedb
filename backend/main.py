from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Server running"}


@app.get("/create")
def create():
    return {"res": "This create endpoint is working!!"}
