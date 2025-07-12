# chatbot-server/chains.py

from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.agents import Tool, AgentExecutor
from langchain.tools import StructuredTool
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.schema import SystemMessage
from langchain.prompts import MessagesPlaceholder
from chatbot_server.vectorstore import get_vectorstore, get_document_sources
from chatbot_server.excel_tools import (
    read_excel_file, update_excel_row, add_excel_row, 
    delete_excel_row, delete_excel_record_by_criteria, get_excel_info as get_excel_info_from_tool
)
from chatbot_server.text_tools import (
    read_text_file, write_to_text_file, append_to_text_file, replace_in_text_file
)
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
import json
from typing import Dict, Any
from contextlib import redirect_stdout
import io
import logging
from pathlib import Path

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
    
    # Check if this is a document capability query
    capability_keywords = ["document filenames", "file types available", "brief content summary", "categories and topics covered"]
    is_capability_query = any(keyword in query.lower() for keyword in capability_keywords)
    
    if is_capability_query:
        # Get all document sources first
        try:
            sources = get_document_sources()
            if not sources:
                return "No documents found in the vector store."
            
            # Sample content from each document source
            vectorstore = get_vectorstore()
            document_summaries = []
            
            for source in sources:
                # Get a sample of content from this specific document
                docs = vectorstore.similarity_search("", k=20, filter={"source": f"/app/pdfs/{source}"})
                if docs:
                    # Get a brief sample of content from this document
                    content_sample = docs[0].page_content[:200] + "..." if len(docs[0].page_content) > 200 else docs[0].page_content
                    document_summaries.append(f"**{source}**: {content_sample}")
            
            return f"Available documents ({len(sources)} total):\n\n" + "\n\n".join(document_summaries)
            
        except Exception as e:
            return f"Error retrieving document sources: {str(e)}"
    
    # === MULTI-STEP VERIFICATION PIPELINE ===
    try:
        # PHASE 1: Intelligent Search and Retrieval
        vectorstore = get_vectorstore()
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        retrieved_docs = retriever.get_relevant_documents(query)
        
        if not retrieved_docs:
            return "I don't have that specific information in my knowledge base."
        
        # PHASE 2: Initial Response Generation
        context = "\n\n".join([doc.page_content for doc in retrieved_docs])
        
        initial_prompt = PromptTemplate.from_template(
            """You are an intelligent assistant. Answer the question using the provided context. Be comprehensive and helpful.

Context:
{context}

Question: {question}

Answer:"""
        )
        
        initial_chain = initial_prompt | llm
        initial_response = initial_chain.invoke({"context": context, "question": query})
        
        # Extract content from LLM response
        if hasattr(initial_response, 'content'):
            initial_answer = initial_response.content
        else:
            initial_answer = str(initial_response)
        
        # PHASE 3: Fact Extraction and Verification
        fact_extraction_prompt = PromptTemplate.from_template(
            """Extract all factual claims from the following text. List each claim as a separate bullet point.
            
Text: {text}

Factual claims:"""
        )
        
        fact_chain = fact_extraction_prompt | llm
        fact_response = fact_chain.invoke({"text": initial_answer})
        
        if hasattr(fact_response, 'content'):
            extracted_facts = fact_response.content
        else:
            extracted_facts = str(fact_response)
        
        # PHASE 4: Verification Against Retrieved Context
        verification_prompt = PromptTemplate.from_template(
            """Given the following context and a list of factual claims, determine which claims are supported by the context.
            
Context:
{context}

Claims to verify:
{claims}

For each claim, respond with either:
- VERIFIED: [claim] - if the claim is supported by the context
- REJECTED: [claim] - if the claim is not supported by the context

Verification results:"""
        )
        
        verification_chain = verification_prompt | llm
        verification_response = verification_chain.invoke({
            "context": context,
            "claims": extracted_facts
        })
        
        if hasattr(verification_response, 'content'):
            verification_results = verification_response.content
        else:
            verification_results = str(verification_response)
        
        # PHASE 5: Strict Context-Only Response
        # Skip the reconstruction phase entirely - use only direct context matching
        context_only_prompt = PromptTemplate.from_template(
            """Answer the question using ONLY the exact information provided in the Context below. 
            
STRICT RULES:
- Use ONLY information that appears word-for-word in the Context
- Do NOT add dates, names, or details not explicitly stated in the Context
- Do NOT make logical inferences or fill in missing information
- Do NOT use any knowledge outside the Context
- If the Context doesn't contain a complete answer, say "Based on the available information:" and list only what's explicitly stated
- If the Context is unrelated, say "I don't have that specific information in my knowledge base."

Context:
{context}

Question: {question}

Answer using only the exact information from the Context above:"""
        )
        
        context_only_chain = context_only_prompt | llm
        final_response = context_only_chain.invoke({
            "question": query,
            "context": context
        })
        
        if hasattr(final_response, 'content'):
            return final_response.content
        else:
            return str(final_response)
            
    except Exception as e:
        # Fallback to simple RAG if verification pipeline fails
        try:
            vectorstore = get_vectorstore()
            retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
            fallback_prompt = PromptTemplate.from_template(
                """Answer the question using only the provided context. If the context doesn't contain the answer, say "I don't have that specific information in my knowledge base."

Context:
{context}

Question: {question}

Answer:"""
            )
            chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever, chain_type_kwargs={"prompt": fallback_prompt})
            return chain.run(query)
        except Exception as fallback_error:
            return f"Error retrieving information: {str(fallback_error)}"

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

def add_new_excel_record(filename: str, order_number: str = "", part_number: str = "", order_details: str = "", price: str = "", seller: str = "", buyer: str = "", **kwargs) -> str:
    """Use this tool to CREATE a new record or add a new row to an Excel file. Provide filename and all the required Excel columns."""
    try:
        # Build the data dict from the parameters
        data = {
            "Order Number": order_number,
            "Part Number": part_number,
            "Order Details": order_details,
            "Price": price,
            "Seller": seller,
            "Buyer": buyer
        }
        
        # Add any additional kwargs
        for k, v in kwargs.items():
            if k not in ["filename"]:  # Skip filename since it's already handled
                data[k] = str(v)
        
        # Remove empty values
        data = {k: v for k, v in data.items() if v.strip()}
        
        result = add_excel_row(filename.strip(), data)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Success: A new row was added to {filename}."
    except Exception as e:
        return f"An unexpected error occurred while adding a row: {str(e)}"

def update_existing_excel_record(filename: str, row_index: int, order_number: str = "", part_number: str = "", order_details: str = "", price: str = "", seller: str = "", buyer: str = "", **kwargs) -> str:
    """Use this tool to UPDATE or MODIFY an existing record in an Excel file. Provide filename, row_index, and the columns to update."""
    try:
        # Build the updates dict from the parameters
        updates = {}
        
        if order_number: updates["Order Number"] = order_number
        if part_number: updates["Part Number"] = part_number
        if order_details: updates["Order Details"] = order_details
        if price: updates["Price"] = price
        if seller: updates["Seller"] = seller
        if buyer: updates["Buyer"] = buyer
        
        # Add any additional kwargs
        for k, v in kwargs.items():
            if k not in ["filename", "row_index"] and v:
                updates[k] = str(v)
        
        if not updates:
            return "Error: No updates provided."
        
        result = update_excel_row(filename.strip(), row_index, updates)
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


def delete_excel_record_smart(filename: str, order_number: str = "", part_number: str = "", order_details: str = "", price: str = "", seller: str = "", buyer: str = "", **kwargs) -> str:
    """Use this tool to DELETE records from an Excel file by matching criteria. Provide filename and the criteria to match for deletion."""
    try:
        # Build the criteria dict from the parameters
        criteria = {}
        
        if order_number: criteria["Order Number"] = order_number
        if part_number: criteria["Part Number"] = part_number
        if order_details: criteria["Order Details"] = order_details
        if price: criteria["Price"] = price
        if seller: criteria["Seller"] = seller
        if buyer: criteria["Buyer"] = buyer
        
        # Add any additional kwargs
        for k, v in kwargs.items():
            if k not in ["filename"] and v:
                criteria[k] = str(v)
        
        if not criteria:
            return "Error: No criteria provided for deletion."
        
        result = delete_excel_record_by_criteria(filename.strip(), criteria)
        if "error" in result:
            return f"Error: {result['error']}"
        return f"Success: {result['message']}"
    except Exception as e:
        return f"An unexpected error occurred while deleting records: {str(e)}"


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
        description="Delete a record from an Excel file by row index.",
    ),
    StructuredTool.from_function(
        func=delete_excel_record_smart,
        name="delete_excel_record_smart",
        description="Delete records from an Excel file by matching criteria (name, account number, etc.). Use this when you know the data values but not the row index.",
    ),
    StructuredTool.from_function(
        func=read_text_file,
        name="read_text_file",
        description="Read the entire content of a text file.",
    ),
    StructuredTool.from_function(
        func=write_to_text_file,
        name="write_to_text_file",
        description="Write content to a text file, overwriting any existing content.",
    ),
    StructuredTool.from_function(
        func=append_to_text_file,
        name="append_to_text_file",
        description="Append content to the end of a text file.",
    ),
    StructuredTool.from_function(
        func=replace_in_text_file,
        name="replace_in_text_file",
        description="Replace all occurrences of a specific string in a text file.",
    )
]

# === Agent and Executor Initialization ===
# The agent prompt and executor are created only once.
system_message = SystemMessage(
    content="""You are a powerful AI business assistant. Your goal is to help the user manage their business by using the tools available to you.

        **Core Reasoning Workflow:**

        **STEP 1: Determine Request Type**
        - **Document Capability Queries** (RAG mode only): User asks about what they can inquire about, available topics, or document summaries (keywords: "what can I ask", "what topics", "summarize", "what do you know about", "what's available", "what can you do", "capabilities", "what can you help", "assist with", "what information", "what data", "what files", "what documents"). This only applies when NOT in Direct GPT mode.
        - **File Operation**: The user wants to add, create, update, delete, read, or modify a file. This includes keywords like "add," "create," "update," "delete," "read," "write," "append," "replace," as well as file extensions like `.xlsx` or `.txt`.
        - **Information Query**: The user is asking a question about existing information. This includes keywords like "what," "who," "how," "summarize," "qualified for," "tell me about."

        **STEP 2: For Document Capability Queries (RAG Mode Only)**
        1.  **Check Mode**: Only proceed if the user is in RAG mode (request does NOT contain "[DIRECT_GPT_MODE]").
        2.  **Progressive Document Discovery**: Perform multiple broad searches to discover all available content:
            - First: Use `find_document_information` with "document filenames and file types available"
            - Then: Use `find_document_information` with "brief content summary of available documents"
            - Finally: Use `find_document_information` with "categories and topics covered in documents"
        3.  **Analyze and Categorize**: Automatically group the search results by content type (resumes, recipes, legal documents, business data, etc.) based on what was discovered.
        4.  **Provide Comprehensive Response**: Summarize all discovered document categories and types, combining both document-specific capabilities AND general information query capabilities.

        **STEP 3: For File Operations**
        1.  **Identify and Confirm File**: First, analyze the user's request to infer the file they want to work on (e.g., `order_inventory.xlsx`, `account_info.xlsx`, `cheeseburger_recipe.txt`). You MUST state your proposed file choice and ask the user for confirmation before proceeding.
        2.  **Determine File Type and Execute**: Once the file is confirmed, check its extension and follow the appropriate workflow.
            - **If `.xlsx` (Excel file):** Follow the "Excel Operations Workflow."
            - **If `.txt` (Text file):** Follow the "Text File Operations Workflow."

        **Excel Operations Workflow**
        1.  **For Deletions**: Use `delete_excel_record_smart` with criteria like `{"Name": "Bob"}` instead of asking for row indices.
        2.  **Gather Information**: Use `get_excel_schema` to see what columns are needed. Ask the user for any details missing from their request (e.g., `Order Number`, `Part Number`).
        3.  **Execute**: Once you have all information, call the appropriate tool (`add_new_excel_record`, `update_existing_excel_record`, `delete_excel_record_smart`).
        4.  **MANDATORY**: You MUST call the tool. Do NOT just say you will do it. Only confirm success AFTER the tool has been called and returned a success message.

        **Text File Operations Workflow**
        1.  **Read and Analyze Format**: First, read the existing file to understand its current format and structure.
        2.  **Identify Action**: Determine if the user wants to read, write, append, or replace.
        3.  **Ask Formatting Questions**: Before making changes, ask the user how they want the content formatted. For example:
            - "Should I add this as a new bullet point in the list format (- item)?"
            - "Should I add this as a new line or append to the existing line?"
            - "Should I maintain the current formatting style?"
        4.  **Gather Content**: Get the exact content and formatting preferences from the user.
        5.  **MANDATORY EXECUTION**: Once you have the content and formatting instructions, you MUST immediately call the appropriate tool (`read_text_file`, `write_to_text_file`, `append_to_text_file`, `replace_in_text_file`). Do NOT ask for confirmation or make a statement before calling the tool. Your ONLY next step is to call the tool.
        6.  **Report Result**: After the tool has been called, report the result (success or error) to the user.

        **STEP 4: For Information Queries**
        1.  **Always Search Documents First**: For ANY information question, ALWAYS call the `find_document_information` tool first with a well-crafted search query. This includes questions about:
            - Municipal services (trash, recycling, parking, schools, etc.)
            - Government services and hours
            - Public transportation
            - Community events
            - Animal control and pet services
            - Any topic that might be covered in local documents
        2.  **Search Strategy**: Even if the question doesn't mention a specific location, search for relevant topics (e.g., "trash pickup" for "when is trash pickup?")
        3.  **Provide Answer**: Give a direct, helpful response based on the document content. If no relevant information is found, then provide a general response.

        **CRITICAL: Information Extraction Rules**
        - "sold by X to Y" means: Seller=X, Buyer=Y
        - "X sold Y to Z" means: Seller=X, Product=Y, Buyer=Z
        - Always extract BOTH seller and buyer information from user requests.

        **Example Multi-Turn Interaction (Excel):**
        User: "Can you add a square sold by greg to ian for $5000?"
        You: "I can help with that. It looks like this is a sales record, so I'll add it to `order_inventory.xlsx`. Is that correct?"
        User: "Yes"
        You: *(Thinking... File confirmed is `order_inventory.xlsx`. It's an Excel file. I will follow the Excel workflow. I need the schema and missing fields.)*
        You: *[Calls get_excel_schema for 'order_inventory.xlsx']*
        You: "Great. To add the record, I also need the Order Number and Part Number. What are they?"
        User: "order number 22, part number 2320232342342"
        You: *(Thinking... Now I have all the data. I will call the 'add' tool.)*
        You: *[Calls add_new_excel_record with filename='order_inventory.xlsx' and complete data: {"Order Number": "22", "Part Number": "2320232342342", "Order Details": "square", "Price": "5000", "Seller": "greg", "Buyer": "ian"}]*
        You: "Thank you. I have successfully added the new record to `order_inventory.xlsx`."

        **Example Information Queries:**
        
        User: "Can you summarize what jobs jordan whitmore is qualified for?"
        You: *(Thinking... This is an information query. I need to search documents.)*
        You: *[Calls find_document_information with query: "Jordan Whitmore qualifications jobs skills experience"]*
        You: "Based on the document, Jordan Whitmore is qualified for [specific jobs/roles based on the search results]."
        
        User: "When is trash pickup?"
        You: *(Thinking... This is asking about municipal services. I should search documents first.)*
        You: *[Calls find_document_information with query: "trash pickup schedule collection days"]*
        You: "Based on the available information, trash pickup occurs on [days/schedule from documents]."
        
        User: "What are the school hours?"
        You: *(Thinking... This is asking about school information. I should search documents.)*
        You: *[Calls find_document_information with query: "school hours schedule"]*
        You: "According to the school information, the hours are [specific hours from documents]."
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
