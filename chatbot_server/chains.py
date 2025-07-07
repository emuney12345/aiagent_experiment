# chatbot-server/chains.py

from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.agents import Tool, AgentExecutor
from langchain.tools import StructuredTool
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.schema import SystemMessage
from langchain.prompts import MessagesPlaceholder
from chatbot_server.vectorstore import get_vectorstore
from chatbot_server.excel_tools import (
    read_excel_file, update_excel_row, add_excel_row, 
    delete_excel_row, get_excel_info
)
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
import json
from typing import Dict, Any

# Using a more capable model is crucial for reliable agentic behavior.
llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, streaming=True)

# --- Tool Definitions ---
# The underlying functions are now updated to accept structured arguments directly.
# The tools are now defined as StructuredTools.

def rag_search_tool(query: str) -> str:
    """Use this to find answers and information from existing documents (like the US Constitution)."""
    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    prompt = PromptTemplate.from_template(
        "You are a helpful assistant. Use the following documents to answer the question.\n\nContext:\n{context}\n\nQuestion: {question}"
    )
    chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever, chain_type_kwargs={"prompt": prompt})
    return chain.run(query)

def get_excel_schema(filename: str) -> str:
    """Use this tool to get the structure, columns, and sample data of an Excel file. This is the first step for any Excel operation to know what columns are available."""
    try:
        return json.dumps(get_excel_info(filename), indent=2)
    except Exception as e:
        return f"Error getting Excel info: {str(e)}"

def read_excel_data(filename: str) -> str:
    """Use this tool to read the current content of an Excel file."""
    try:
        result = read_excel_file(filename)
        return f"File '{filename}' has {result['rows']} rows, columns: {result['columns']}. Data: {json.dumps(result['data'][:5], indent=2)}"
    except Exception as e:
        return f"Error reading Excel file: {str(e)}"

def add_new_excel_record(filename: str, data: Dict[str, Any]) -> str:
    """Use this tool to CREATE a new record or add a new row to an Excel file. The 'data' argument should be a dictionary where keys are the column names and values are the data to be added."""
    try:
        # Enforce string type for all data to ensure consistency
        data_as_str = {k: str(v) for k, v in data.items()}
        result = add_excel_row(filename.strip(), data_as_str)
        return f"✅ Successfully added new row to {filename}: {result.get('message', '')}"
    except Exception as e:
        return f"Error adding Excel row: {str(e)}"

def update_existing_excel_record(filename: str, row_index: int, updates: Dict[str, Any]) -> str:
    """Use this tool to UPDATE or MODIFY an existing record in an Excel file. The 'updates' argument is a dictionary of the changes to make."""
    try:
        # Enforce string type for all data to ensure consistency
        updates_as_str = {k: str(v) for k, v in updates.items()}
        result = update_excel_row(filename.strip(), row_index, updates_as_str)
        return f"✅ Successfully updated row in {filename}: {result.get('message', '')}"
    except Exception as e:
        return f"Error updating Excel row: {str(e)}"

def delete_excel_record(filename: str, row_index: int) -> str:
    """Use this tool to DELETE or REMOVE a record from an Excel file."""
    try:
        result = delete_excel_row(filename.strip(), row_index)
        return f"✅ Successfully deleted row from {filename}: {result.get('message', '')}"
    except Exception as e:
        return f"Error deleting Excel row: {str(e)}"

tools = [
    Tool(name="find_document_information", func=rag_search_tool, description="Find answers from existing documents."),
    StructuredTool.from_function(
        func=get_excel_schema,
        name="get_excel_schema",
        description="Get the structure and columns of an Excel file.",
    ),
    StructuredTool.from_function(
        func=read_excel_data,
        name="read_excel_data",
        description="Read data from an Excel file.",
    ),
    StructuredTool.from_function(
        func=add_new_excel_record,
        name="add_new_excel_record",
        description="Create a new record in an Excel file. Use this when the user wants to add or create new information.",
    ),
    StructuredTool.from_function(
        func=update_existing_excel_record,
        name="update_existing_excel_record",
        description="Update an existing record in an Excel file. Use this for modifying existing data.",
    ),
    StructuredTool.from_function(
        func=delete_excel_record,
        name="delete_excel_record",
        description="Delete a record from an Excel file.",
    )
]

# --- Main Agentic Chain ---

session_memory = {}

def run_chat_chain(question: str, session_id: str = "default") -> str:
    """Runs the main conversational agent chain using the highly reliable OpenAI Functions Agent."""
    
    if session_id not in session_memory:
        session_memory[session_id] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    memory = session_memory[session_id]

    system_message = SystemMessage(
        content="""You are a powerful AI business assistant. Your goal is to help the user manage their business by using the tools available to you.

        **Core Instructions:**
        1.  **Intent Analysis**: Understand if the user wants to READ existing info or WRITE/MODIFY info.
        2.  **Tool Selection**:
            *   For READ requests (e.g., "what is", "show me"), use `find_document_information` or `read_excel_data`.
            *   For WRITE/MODIFY requests (e.g., "add a record", "create an entry"), you MUST use `add_new_excel_record`, `update_existing_excel_record`, or `delete_excel_record`.
        3.  **Mandatory Excel Workflow**:
            a.  **Schema First**: Before any write operation, you MUST use `get_excel_schema` to know the file's columns.
            b.  **Gather Information**: If the user has not provided all necessary columns, you MUST ask for the missing information. Use your memory of the conversation to know what you already have. Do not make up data.
            c.  **Execute**: Once you have all required information (from one or more user messages), call the appropriate tool (`add_new_excel_record`, etc.).
            d.  **Confirm**: After the tool runs, confirm to the user that the action was successful.
        
        **Example Multi-Turn Interaction:**
        User: "Can you add a record where Matt sold Tom an inflatable boat for $500?"
        You: *(Thinking... This is a WRITE request. I must add a record. First, check the schema.)*
        You: *[Calls get_excel_schema for 'order_inventory.xlsx']*
        You: *[Sees the columns: 'Order_Number', 'Part_Number', 'Order_Details', etc.]*
        You: *[Compares provided info to columns and sees 'Order_Number' and 'Part_Number' are missing.]*
        You: "I can do that, but I need the Order Number and Part Number for this transaction. What are they?"
        User: "The order number is 6 and the part number is BOAT-001"
        You: *[Remembers the previous details about Matt, Tom, the boat, and the price from memory. Combines it with the new info.]*
        You: *[Calls add_new_excel_record with structured arguments: filename='order_inventory.xlsx', data={"Order_Number": "6", "Part_Number": "BOAT-001", "Seller": "Matt", ...}]*
        You: "Thank you. I have successfully added the new record to order_inventory.xlsx."
        """
    )

    prompt = OpenAIFunctionsAgent.create_prompt(
        system_message=system_message,
        extra_prompt_messages=[MessagesPlaceholder(variable_name="chat_history")]
    )

    agent = OpenAIFunctionsAgent(llm=llm, tools=tools, prompt=prompt)

    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        memory=memory, 
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15
    )

    try:
        result = agent_executor.invoke({"input": question})
        return result.get("output", "I'm sorry, I encountered an error.")
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(error_message)
        return error_message
