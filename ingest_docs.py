# ingest_docs.py

from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from chatbot_server.vectorstore import get_vectorstore

loader = PyPDFLoader("pdfs/US_Constitution-Senate_Publication_103-21.pdf")
docs = loader.load_and_split()

vectorstore = get_vectorstore()
vectorstore.add_documents(docs)

print("✅ Document ingestion complete using PGVector.")
