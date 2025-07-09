# chatbot-server/main.py

from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from chatbot_server.chains import run_chat_chain
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import os
import shutil
from dotenv import load_dotenv
from openai import OpenAI
from typing import List

load_dotenv()

app = FastAPI()

# === CORS middleware ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500", "http://127.0.0.1:8001", "http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PDFS_DIR = "pdfs"
os.makedirs(PDFS_DIR, exist_ok=True)

# === Request model ===
class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"

@app.post("/chat")
async def chat(request: ChatRequest):
    # Check if this is a direct GPT mode request
    if request.question.startswith("[DIRECT_GPT_MODE]"):
        # Strip the prefix and use direct GPT
        clean_question = request.question.replace("[DIRECT_GPT_MODE]", "").strip()
        response = query_openai_direct(clean_question)
    else:
        # Use the enhanced RAG + Excel chain
        response = run_chat_chain(request.question, session_id=request.session_id)

    # Fallback to direct GPT if response is unhelpful
    if is_unhelpful(response):
        response = query_openai_direct(request.question)

    store_chat(request.session_id, request.question, response)
    return {"response": response}

@app.get("/history/{session_id}")
async def get_history(session_id: str):
    history = fetch_history(session_id)
    return {"history": history}

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    results = []
    success_count = 0
    for file in files:
        safe_filename = os.path.basename(file.filename)
        file_path = os.path.join(PDFS_DIR, safe_filename)

        try:
            if not safe_filename:
                # This will be caught by the exception handler below
                raise ValueError("Invalid filename provided")

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            results.append({"filename": safe_filename, "detail": "File uploaded successfully"})
            success_count += 1
        except Exception as e:
            error_message = f"Could not save file: {e}"
            print(f"Error saving file '{file.filename}': {error_message}")
            results.append({"filename": file.filename or "unknown", "error": error_message})
        finally:
            if file:
                file.file.close()
    
    if success_count == 0 and results:
        # If no files succeeded, return the first error as the detail in a 500 response
        raise HTTPException(status_code=500, detail=results[0].get("error", "File upload failed"))
        
    return {"results": results}


# === Config ===
MAX_HISTORY_PROMPTS = 20  # each prompt = 1 user + 1 bot entry

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
            # Insert both user and assistant messages
            cur.execute(
                """
                INSERT INTO chat_history (session_id, role, answer)
                VALUES (%s, %s, %s), (%s, %s, %s)
                """,
                (session_id, 'user', question, session_id, 'assistant', answer)
            )

            # Trim chat to keep only latest N pairs (2N rows)
            cur.execute(
                """
                DELETE FROM chat_history
                WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id FROM chat_history
                        WHERE session_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    ) AS latest
                ) AND session_id = %s
                """,
                (session_id, MAX_HISTORY_PROMPTS * 2, session_id)
            )

def fetch_history(session_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, answer
                FROM chat_history
                WHERE session_id = %s
                ORDER BY created_at ASC, id ASC
                LIMIT %s
                """,
                (session_id, MAX_HISTORY_PROMPTS * 2)
            )
            return [{"role": r, "answer": a} for r, a in cur.fetchall()]

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
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return completion.choices[0].message.content.strip()
