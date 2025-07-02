# chatbot-server/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from chatbot_server.chains import run_chat_chain
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = FastAPI()

# === CORS middleware ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Request model ===
class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"

# === Routes ===
@app.post("/chat")
async def chat(request: ChatRequest):
    response = run_chat_chain(request.question, session_id=request.session_id)

    # Fallback if RAG result is unhelpful
    if is_unhelpful(response):
        response = query_openai_direct(request.question)

    store_chat(request.session_id, request.question, response)
    return {"response": response}

@app.get("/history/{session_id}")
async def get_history(session_id: str):
    history = fetch_history(session_id)
    return {"history": history}

# === Database config ===
MAX_HISTORY_PER_SESSION = 20

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "chatbot_db")
DB_USER = os.getenv("POSTGRES_USER", "user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "securepass123")

def get_conn():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

def store_chat(session_id: str, question: str, answer: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_history (session_id, role, answer)
                VALUES (%s, %s, %s)
                """,
                (session_id, 'user', question)
            )
            cur.execute(
                """
                INSERT INTO chat_history (session_id, role, answer)
                VALUES (%s, %s, %s)
                """,
                (session_id, 'assistant', answer)
            )
            cur.execute(
                """
                DELETE FROM chat_history
                WHERE id IN (
                    SELECT id FROM chat_history
                    WHERE session_id = %s
                    ORDER BY created_at ASC
                    OFFSET %s
                )
                """,
                (session_id, MAX_HISTORY_PER_SESSION * 2)
            )

def fetch_history(session_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, answer
                FROM chat_history
                WHERE session_id = %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (session_id, MAX_HISTORY_PER_SESSION * 2)
            )
            return [{"role": r, "answer": a} for r, a in cur.fetchall()]

# === Fallback logic ===
def is_unhelpful(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in [
        "i'm sorry",
        "not in the documents",
        "do not contain information",
        "would you like me to search",
        "no specific question mentioned",
        "need assistance with a specific topic"
    ])


def query_openai_direct(prompt: str) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model  = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return completion.choices[0].message.content.strip()
