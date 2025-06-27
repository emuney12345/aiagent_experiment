# chatbot-server/chains.py

from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from vectorstore import get_vectorstore
from langchain.prompts import PromptTemplate

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

def run_chat_chain(question: str, session_id: str = "default") -> str:
    vectorstore = get_vectorstore()

    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    prompt = PromptTemplate.from_template("""
    You are a helpful government-grade assistant. Use the following documents to answer the question.
    
    Context:
    {context}
    
    Question: {question}
    """)

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=False,
        chain_type_kwargs={"prompt": prompt}
    )

    result = chain.run(question)
    return result
