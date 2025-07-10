# chatbot-server/vectorstore.py

import os
from pathlib import Path
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

def get_document_sources():
    """Get all unique document sources from the vector store"""
    vs = get_vectorstore()
    # Query with a very broad search to get diverse results
    docs = vs.similarity_search("", k=100)  # Get many results
    sources = set()
    for doc in docs:
        if 'source' in doc.metadata:
            sources.add(Path(doc.metadata['source']).name)
    return list(sources)
