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
    delete_excel_row, get_excel_info as get_excel_info_from_tool
)
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
import json
from typing import Dict, Any
from contextlib import redirect_stdout
import io
import logging

# === Logging Configuration ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# === Global objects ===
# These are initialized once and reused across requests.
llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, streaming=True)
session_memory = {}  # Dictionary to hold memory for each session_id

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
        return json.dumps(get_excel_info_from_tool(filename), indent=2)
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
        data_as_str = {k: str(v) for k, v in data.items()}
        result = add_excel_row(filename.strip(), data_as_str)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Success: A new row was added to {filename}."
    except Exception as e:
        return f"An unexpected error occurred while adding a row: {str(e)}"

def update_existing_excel_record(filename: str, row_index: int, updates: Dict[str, Any]) -> str:
    """Use this tool to UPDATE or MODIFY an existing record in an Excel file. The 'updates' argument is a dictionary of the changes to make."""
    try:
        updates_as_str = {k: str(v) for k, v in updates.items()}
        result = update_excel_row(filename.strip(), row_index, updates_as_str)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Success: Row {row_index} in {filename} was updated."
    except Exception as e:
        return f"An unexpected error occurred while updating a row: {str(e)}"


def delete_excel_record(filename: str, row_index: int) -> str:
    """Use this tool to DELETE an existing record in an Excel file by its row index."""
    try:
        result = delete_excel_row(filename.strip(), row_index)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Success: Row {row_index} in {filename} was deleted."
    except Exception as e:
        return f"An unexpected error occurred while deleting a row: {str(e)}"


# A helper function to get the schema of an excel file to help with creating new rows
def get_excel_info(filename: str) -> str:
    """Use this tool to get the schema of an Excel file, which can help with creating or updating records."""
    try:
        # This now correctly calls the imported function from excel_tools.py
        return json.dumps(get_excel_info_from_tool(filename.strip()), indent=2)
    except Exception as e:
        return f"Error getting Excel info: {str(e)}"

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

# === Agent and Executor Initialization ===
# The agent prompt and executor are created only once.
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
        c.  **Construct the Final Record**: When you have all the data, you must create a dictionary for the `add_new_excel_record` tool. The keys of this dictionary MUST exactly match the column names from the schema. For example, the description of the item must be under the key "Order Details".
        d.  **Execute**: Once you have all required information (from one or more user messages), call the appropriate tool (`add_new_excel_record`, etc.).
        e.  **Confirm**: After the tool runs, confirm to the user that the action was successful.
    
    **Example Multi-Turn Interaction:**
    User: "Can you add a record where Matt sold Tom an inflatable boat for $500?"
    You: *(Thinking... This is a WRITE request. I must add a record. First, check the schema.)*
    You: *[Calls get_excel_schema for 'order_inventory.xlsx']*
    You: *[Sees the columns: 'Order_Number', 'Part_Number', 'Order_Details', etc.]*
    You: *[Compares provided info to columns and sees 'Order_Number' and 'Part_Number' are missing.]*
    You: "I can do that, but I need the Order Number and Part Number for this transaction. What are they?"
    User: "The order number is 6 and the part number is BOAT-001"
    You: *[Remembers the previous details about Matt, Tom, the boat, and the price from memory. Combines it with the new info.]*
    You: *[Calls add_new_excel_record with structured arguments: filename='order_inventory.xlsx', data={"Order_Number": "6", "Part_Number": "BOAT-001", "Order Details": "inflatable boat", "Seller": "Matt", ...}]*
    You: "Thank you. I have successfully added the new record to order_inventory.xlsx."
    """
)

prompt = OpenAIFunctionsAgent.create_prompt(
    system_message=system_message,
    extra_prompt_messages=[MessagesPlaceholder(variable_name="chat_history")]
)

agent = OpenAIFunctionsAgent(llm=llm, tools=tools, prompt=prompt)

# --- Main Agentic Chain ---

def run_chat_chain(question: str, session_id: str = "default") -> str:
    """
    Runs the chat chain for a given question and session ID.
    Manages memory per session and captures agent's thought process.
    """
    logger.info(f"Received question for session {session_id}: {question}")

    # Get or create memory for the given session
    if session_id not in session_memory:
        session_memory[session_id] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    memory = session_memory[session_id]
    
    # Create a new agent executor for each request to ensure memory is handled correctly
    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools, 
        memory=memory, 
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15
    )

    try:
        # Capture the verbose output from the agent's execution
        string_io = io.StringIO()
        with redirect_stdout(string_io):
            response = agent_executor.run(question)
        
        thought_process = string_io.getvalue()
        
        # Log the captured thought process for analysis
        logger.info("--- AGENT THOUGHT PROCESS ---")
        logger.info(thought_process)
        logger.info("-----------------------------")
        
        return response
    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return error_message


if __name__ == '__main__':
    # Example usage (for debugging purposes)
    print(run_chat_chain("Can you add a record where Matt sold Tom an inflatable boat for $500?", "test_session"))
    print(run_chat_chain("What is the price of the inflatable boat?", "test_session"))
