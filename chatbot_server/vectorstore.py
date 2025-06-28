# chatbot-server/vectorstore.py

import os
from langchain_community.vectorstores import PGVector
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

# ✅ Explicitly load the .env file from the root of the Docker container
load_dotenv(dotenv_path="/app/.env")  # 👈 FIXED

COLLECTION_NAME = "chatbot_docs"

def get_vectorstore():
    connection_string = os.getenv("DATABASE_URL")  # Example: postgresql://user:pass@localhost:5432/chatbot_db
    embeddings = OpenAIEmbeddings()

    return PGVector(
        connection_string=connection_string,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings
    )
