# chatbot-server/chains.py

from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.agents import initialize_agent, Tool, AgentType, create_openai_functions_agent
from langchain.agents.agent import AgentExecutor
from langchain.schema import SystemMessage
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from chatbot_server.vectorstore import get_vectorstore
from chatbot_server.excel_tools import (
    read_excel_file, update_excel_row, add_excel_row, 
    delete_excel_row, get_excel_info
)
from langchain.prompts import PromptTemplate
import json

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

def rag_search_tool(query: str) -> str:
    """Tool for RAG-based document search."""
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

    result = chain.run(query)
    return result

def excel_read_tool(filename: str) -> str:
    """Tool for reading Excel files."""
    try:
        result = read_excel_file(filename)
        return f"Excel file '{filename}' contains {result['rows']} rows with columns: {result['columns']}. Sample data: {result['data'][:3] if result['data'] else 'No data'}"
    except Exception as e:
        return f"Error reading Excel file: {str(e)}"

def excel_info_tool(filename: str) -> str:
    """Tool for getting Excel file structure information."""
    try:
        result = get_excel_info(filename)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error getting Excel info: {str(e)}"

def excel_update_tool(input_str: str) -> str:
    """Tool for updating Excel rows. Input format: 'filename|row_index|JSON_data'"""
    try:
        parts = input_str.split('|', 2)
        if len(parts) != 3:
            return "Error: Input must be in format 'filename|row_index|JSON_data'. Example: 'order_inventory.xlsx|0|{\"Price\": \"150\"}'"
        
        filename, row_index_str, updates = parts
        filename = filename.strip()
        row_index = int(row_index_str.strip())
        updates = updates.strip()
        
        updates_dict = json.loads(updates)
        result = update_excel_row(filename, row_index, updates_dict)
        return f"Successfully updated row {row_index} in {filename}: {result['message']}"
    except Exception as e:
        return f"Error updating Excel row: {str(e)}"

def excel_add_tool(input_str: str) -> str:
    """Tool for adding new rows to Excel. Input format: 'filename|JSON_data'"""
    try:
        if '|' not in input_str:
            return "Error: Input must be in format 'filename|JSON_data'. Example: 'order_inventory.xlsx|{\"Order_Number\": \"5\", \"Seller\": \"Brian\"}'"
        
        filename, new_data = input_str.split('|', 1)
        filename = filename.strip()
        new_data = new_data.strip()
        
        new_data_dict = json.loads(new_data)
        result = add_excel_row(filename, new_data_dict)
        return f"Successfully added new row to {filename}: {result['message']}"
    except Exception as e:
        return f"Error adding Excel row: {str(e)}"

def excel_delete_tool(input_str: str) -> str:
    """Tool for deleting rows from Excel. Input format: 'filename|row_index'"""
    try:
        if '|' not in input_str:
            return "Error: Input must be in format 'filename|row_index'. Example: 'order_inventory.xlsx|0'"
        
        filename, row_index_str = input_str.split('|', 1)
        filename = filename.strip()
        row_index = int(row_index_str.strip())
        
        result = delete_excel_row(filename, row_index)
        return f"Successfully deleted row {row_index} from {filename}: {result['message']}"
    except Exception as e:
        return f"Error deleting Excel row: {str(e)}"

# Define tools for the agent
tools = [
    Tool(
        name="rag_search",
        func=rag_search_tool,
        description="Search through ingested documents and PDFs for information. Use for questions about document content, government information, Constitution, etc."
    ),
    Tool(
        name="excel_info",
        func=excel_info_tool,
        description="Get Excel file structure information. Input: filename like 'account_info.xlsx' or 'order_inventory.xlsx'. This shows you what columns are available."
    ),
    Tool(
        name="excel_read",
        func=excel_read_tool,
        description="Read Excel file content. Input: filename like 'account_info.xlsx' or 'order_inventory.xlsx'. Use this to see existing data."
    ),
    Tool(
        name="excel_add",
        func=excel_add_tool,
        description="MANDATORY for adding new rows to Excel files. When user says 'add order' or 'add new entry', you MUST use this tool. Input format: 'filename|JSON_data'. Example: 'order_inventory.xlsx|{\"Order_Number\": \"5\", \"Seller\": \"Brian\", \"Buyer\": \"Tom\", \"Item\": \"GoPro\", \"Price\": \"100\"}'. This tool actually modifies the Excel file."
    ),
    Tool(
        name="excel_update",
        func=excel_update_tool,
        description="Update existing rows in Excel files. Input format: 'filename|row_index|JSON_data'. Example: 'order_inventory.xlsx|0|{\"Price\": \"150\"}'. Row index is 0-based."
    ),
    Tool(
        name="excel_delete",
        func=excel_delete_tool,
        description="Delete rows from Excel files. Input format: 'filename|row_index'. Example: 'order_inventory.xlsx|0'. Row index is 0-based."
    )
]

def is_excel_operation(question: str) -> bool:
    """Detect if the question is about Excel operations."""
    excel_keywords = [
        "add order", "add new", "update order", "update inventory", 
        "delete order", "remove order", "modify order", "change order",
        "new order", "order number", "brian sold", "tom bought", 
        "gopro", "inventory", "price", "seller", "buyer"
    ]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in excel_keywords)

def run_chat_chain(question: str, session_id: str = "default") -> str:
    """Main function that handles both RAG and Excel operations using proper agentic AI."""
    
    # Try the agentic approach first (more scalable)
    try:
        return run_agentic_approach(question)
    except Exception as e:
        print(f"Agent failed: {e}")
        # Fallback to direct approach for Excel operations
        if is_excel_operation(question):
            return handle_excel_operation_directly(question)
        else:
            return rag_search_tool(question)

def run_agentic_approach(question: str) -> str:
    """Proper agentic AI approach using improved agent configuration."""
    
    # Create a more sophisticated agent with better prompting
    system_message = """You are an intelligent business assistant with access to tools for document search and Excel file management.

IMPORTANT: You must ACTUALLY USE the tools when requested, not just describe what you would do.

Your capabilities:
- Search documents using rag_search
- Manage Excel files (account_info.xlsx, order_inventory.xlsx) using Excel tools
- Extract information from user requests intelligently

When a user asks for Excel operations:
1. Use excel_info to understand file structure
2. Use appropriate Excel tools (excel_add, excel_update, excel_read, excel_delete)
3. Confirm the action was completed

Examples of requests that need Excel tools:
- "Add a new order..." → Use excel_add
- "Update order..." → Use excel_update  
- "Show me the inventory..." → Use excel_read
- "Delete order..." → Use excel_delete

You are intelligent and can handle new types of requests by choosing the appropriate tools."""

    # Create the agent with improved configuration
    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15,
        early_stopping_method="generate"
    )
    
    # Enhanced prompt that forces action
    enhanced_prompt = f"""
    {system_message}
    
    User request: {question}
    
    Remember: You must actually use the tools to complete the request. Do not just describe what you would do.
    
    If this is about Excel operations, use the Excel tools.
    If this is about document content, use rag_search.
    """
    
    return agent.run(enhanced_prompt)

def handle_excel_operation_directly(question: str) -> str:
    """Handle Excel operations directly without relying on agent decision-making."""
    
    question_lower = question.lower()
    
    # Detect if this is an ADD operation
    if any(keyword in question_lower for keyword in ["add", "new order", "brian sold", "selling"]):
        return handle_add_operation(question)
    
    # Detect if this is an UPDATE operation  
    elif any(keyword in question_lower for keyword in ["update", "change", "modify"]):
        return handle_update_operation(question)
    
    # Detect if this is a READ operation
    elif any(keyword in question_lower for keyword in ["show", "read", "what's in", "display"]):
        return handle_read_operation(question)
    
    # Default to add operation if unclear
    else:
        return handle_add_operation(question)

def handle_add_operation(question: str) -> str:
    """Handle adding new rows to Excel files."""
    
    try:
        # Get file structure first
        file_info = get_excel_info("order_inventory.xlsx")
        
        # Extract information from the question using AI
        extraction_prompt = f"""
        Extract the following information from this user request about adding an order:
        
        User request: {question}
        
        Available columns in order_inventory.xlsx: {file_info.get('sheet_info', {}).get('Sheet1', {}).get('columns', [])}
        
        Please extract values and return ONLY a JSON object with the column names and values.
        Example format: {{"Order_Number": "5", "Seller": "Brian", "Buyer": "Tom", "Item": "GoPro", "Price": "100"}}
        
        If any information is missing, use reasonable defaults or ask for clarification.
        """
        
        # Use OpenAI directly for extraction
        extraction_result = llm.invoke(extraction_prompt).content.strip()
        
        # Try to parse the JSON from the extraction
        try:
            import re
            json_match = re.search(r'\{.*\}', extraction_result, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                extracted_data = json.loads(json_str)
                
                # Actually add the row
                add_result = add_excel_row("order_inventory.xlsx", extracted_data)
                
                return f"✅ I have successfully added this row to order_inventory.xlsx: {extracted_data}. {add_result.get('message', '')}"
            else:
                return f"❌ Could not extract order information from your request. Please provide: order number, seller, buyer, item, and price."
                
        except Exception as parse_error:
            return f"❌ Error parsing order information: {str(parse_error)}. Please provide: order number, seller, buyer, item, and price."
            
    except Exception as e:
        return f"❌ Error adding to Excel file: {str(e)}"

def handle_update_operation(question: str) -> str:
    """Handle updating existing rows in Excel files."""
    return "📝 Update operations are not yet implemented. Please specify which row to update and the new values."

def handle_read_operation(question: str) -> str:
    """Handle reading Excel files."""
    try:
        result = read_excel_file("order_inventory.xlsx")
        return f"📊 Current order inventory data:\n\nColumns: {result['columns']}\nRows: {result['rows']}\n\nData:\n{json.dumps(result['data'], indent=2)}"
    except Exception as e:
        return f"❌ Error reading Excel file: {str(e)}"
