from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "LedyBot is alive and ready to shine!"}