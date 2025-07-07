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

        **Core Reasoning Workflow:**
        
        **STEP 1: Determine Request Type**
        - **Excel Operations**: User wants to add, update, delete, or modify data (keywords: "add", "create", "update", "delete", "sold by", "bought", "order")
        - **Information Queries**: User asks questions about existing information (keywords: "what", "who", "how", "summarize", "qualified for", "tell me about")
        
        **STEP 2A: For Excel Operations**
        1.  **Identify and Confirm File**: Analyze the user's request to infer the topic (`sales` vs. `accounts`) and the corresponding file (`order_inventory.xlsx` vs. `account_info.xlsx`). You MUST state your choice and ask the user for confirmation before proceeding.

        2.  **Gather and Execute**: Once the file is confirmed, your only goal is to gather the information needed and add it to the file.
            a.  Use `get_excel_schema` to understand the required columns.
            b.  Ask the user for any details missing from their request (e.g., `Order Number`, `Part Number`).
            c.  **MANDATORY**: Once you have all the information, you MUST call the `add_new_excel_record` tool. Do NOT just say you will do it - ACTUALLY DO IT.
            d.  **Assemble the Full Record**: You must construct a complete `data` dictionary using all the information you have gathered from the user across the conversation.
            e.  **Call the Tool**: Call `add_new_excel_record` with the `filename` and the complete `data` dictionary.
            f.  **NEVER claim success without calling the tool first**: Only say "successfully added" AFTER you have actually called the tool and received a success response.

        **STEP 2B: For Information Queries**
        1.  **Use Document Search**: Call the `find_document_information` tool with a well-crafted search query.
        2.  **Extract Key Information**: Parse the results to find the specific information requested.
        3.  **Provide Clear Answer**: Give a direct, helpful response based on the document content.

        **CRITICAL: Information Extraction Rules**
        - "sold by X to Y" means: Seller=X, Buyer=Y
        - "X sold Y to Z" means: Seller=X, Product=Y, Buyer=Z
        - Always extract BOTH seller and buyer information from user requests

        **Example Multi-Turn Interaction:**
        User: "Can you add a square sold by greg to ian for $5000?"
        You: "I can help with that. It looks like this is a sales record, so I'll add it to `order_inventory.xlsx`. Is that correct?"
        User: "Yes"
        You: *(Thinking... The file is confirmed. I extracted: Seller=greg, Buyer=ian, Product=square, Price=5000. Now I need schema and missing fields.)*
        You: *[Calls get_excel_schema for 'order_inventory.xlsx']*
        You: "Great. To add the record, I also need the Order Number and Part Number. What are they?"
        User: "order number 22, part number 2320232342342"
        You: *(Thinking... Now I have all the data. I will call the 'add' tool with ALL information including seller.)*
        You: *[Calls add_new_excel_record with filename='order_inventory.xlsx' and complete data: {"Order Number": "22", "Part Number": "2320232342342", "Order Details": "square", "Price": "5000", "Seller": "greg", "Buyer": "ian"}]*
        You: "Thank you. I have successfully added the new record to `order_inventory.xlsx`."

        **Example Information Query:**
        User: "Can you summarize what jobs jordan whitmore is qualified for?"
        You: *(Thinking... This is an information query about Jordan Whitmore. I need to search documents.)*
        You: *[Calls find_document_information with query: "Jordan Whitmore qualifications jobs skills experience"]*
        You: "Based on the document, Jordan Whitmore is qualified for [specific jobs/roles based on the search results]."
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
            # Use the modern .invoke() method, which is designed for correct memory handling.
            # The deprecated .run() method does not reliably update the memory object.
            result = agent_executor.invoke({"input": question})
            response = result.get("output", "I'm sorry, I encountered an error.")
        
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
