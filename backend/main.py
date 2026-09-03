from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "KSL-Tube backend is running"}