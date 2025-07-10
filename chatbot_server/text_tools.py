
import os
from typing import List

# Define the base directory for text files (Docker container path)
TEXT_FILES_DIR = "/app/pdfs"

def _get_text_file_path(filename: str) -> str:
    """Get full path to text file."""
    # If it's already an absolute path, use it as-is
    if os.path.isabs(filename):
        return filename
    
    # Otherwise, construct path relative to the text files directory
    return os.path.join(TEXT_FILES_DIR, filename)

def read_text_file(file_path: str) -> str:
    """
    Reads the content of a text file.

    Args:
        file_path (str): The path to the text file.

    Returns:
        str: The content of the file, or an error message if the file cannot be read.
    """
    try:
        full_path = _get_text_file_path(file_path)
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_to_text_file(file_path: str, content: str) -> str:
    """
    Writes content to a text file, overwriting any existing content.

    Args:
        file_path (str): The path to the text file.
        content (str): The content to write to the file.

    Returns:
        str: A success message or an error message.
    """
    try:
        full_path = _get_text_file_path(file_path)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Verify the write was successful by reading back the content
        with open(full_path, 'r', encoding='utf-8') as f:
            written_content = f.read()
        
        if written_content == content:
            return f"Successfully wrote to {file_path} (verified: {len(content)} characters)"
        else:
            return f"Error: Write operation failed - content verification failed for {file_path}"
            
    except Exception as e:
        return f"Error writing to file: {e}"

def append_to_text_file(file_path: str, content: str) -> str:
    """
    Appends content to an existing text file.

    Args:
        file_path (str): The path to the text file.
        content (str): The content to append.

    Returns:
        str: A success message or an error message.
    """
    try:
        full_path = _get_text_file_path(file_path)
        
        # Read original content first
        original_content = ""
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
        
        # Append the new content
        with open(full_path, 'a', encoding='utf-8') as f:
            f.write(content)
        
        # Verify the append was successful
        with open(full_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
        
        expected_content = original_content + content
        if new_content == expected_content:
            return f"Successfully appended to {file_path} (verified: added {len(content)} characters)"
        else:
            return f"Error: Append operation failed - content verification failed for {file_path}"
            
    except Exception as e:
        return f"Error appending to file: {e}"

def replace_in_text_file(file_path: str, old_string: str, new_string: str) -> str:
    """
    Replaces all occurrences of a string in a text file.

    Args:
        file_path (str): The path to the text file.
        old_string (str): The string to be replaced.
        new_string (str): The string to replace with.

    Returns:
        str: A success message indicating how many replacements were made, or an error message.
    """
    try:
        full_path = _get_text_file_path(file_path)
        
        if not os.path.exists(full_path):
            return f"Error: File {file_path} does not exist"
        
        with open(full_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        replacements_count = file_content.count(old_string)
        if replacements_count == 0:
            return f"The string '{old_string}' was not found in {file_path}. No changes made."

        new_content = file_content.replace(old_string, new_string)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # Verify the replacement was successful
        with open(full_path, 'r', encoding='utf-8') as f:
            written_content = f.read()
        
        if written_content == new_content:
            return f"Successfully replaced {replacements_count} instance(s) of '{old_string}' with '{new_string}' in {file_path} (verified)"
        else:
            return f"Error: Replace operation failed - content verification failed for {file_path}"
            
    except Exception as e:
        return f"Error processing file: {e}" 