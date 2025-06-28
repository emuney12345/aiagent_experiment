# chatbot-server/models/document.py

from pydantic import BaseModel

class Document(BaseModel):
    title: str
    content: str
    source: str
