# chatbot-server/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from chains import run_chat_chain
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Optional: for local frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"

@app.post("/chat")
async def chat(request: ChatRequest):
    response = run_chat_chain(request.question, session_id=request.session_id)
    return {"response": response}
