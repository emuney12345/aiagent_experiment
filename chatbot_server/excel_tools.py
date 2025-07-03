import pandas as pd
import openpyxl
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

# Set up logging for Excel operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define allowed Excel files for safety
ALLOWED_EXCEL_FILES = [
    "account_info.xlsx",
    "order_inventory.xlsx"
]

EXCEL_DIR = "/app/pdfs"  # Docker container path

def _get_excel_path(filename: str) -> str:
    """Get full path to Excel file and validate it's allowed."""
    if filename not in ALLOWED_EXCEL_FILES:
        raise ValueError(f"Excel file '{filename}' not allowed. Allowed files: {ALLOWED_EXCEL_FILES}")
    
    filepath = os.path.join(EXCEL_DIR, filename)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Excel file not found: {filepath}")
    
    return filepath

def _log_operation(operation: str, filename: str, details: str):
    """Log Excel operations for traceability."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {operation} on {filename}: {details}"
    logger.info(log_message)
    
    # Also write to a dedicated log file
    try:
        with open("/app/excel_operations.log", "a") as f:
            f.write(log_message + "\n")
    except Exception as e:
        logger.error(f"Failed to write to log file: {e}")

def read_excel_file(filename: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Read Excel file and return its contents as a dictionary.
    
    Args:
        filename: Name of the Excel file
        sheet_name: Specific sheet to read (optional)
    
    Returns:
        Dict containing file info and data
    """
    filepath = _get_excel_path(filename)
    
    try:
        if sheet_name:
            df = pd.read_excel(filepath, sheet_name=sheet_name)
            sheets = [sheet_name]
        else:
            # Read all sheets
            excel_file = pd.ExcelFile(filepath)
            sheets = excel_file.sheet_names
            df = pd.read_excel(filepath, sheet_name=sheets[0])  # Default to first sheet
        
        _log_operation("READ", filename, f"Read {len(df)} rows from sheet(s): {sheets}")
        
        return {
            "filename": filename,
            "sheets": sheets,
            "current_sheet": sheet_name or sheets[0],
            "rows": len(df),
            "columns": df.columns.tolist(),
            "data": df.to_dict('records')
        }
    
    except Exception as e:
        error_msg = f"Error reading Excel file: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)

def update_excel_row(filename: str, row_index: int, updates: Dict[str, Any], sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Update a specific row in Excel file.
    
    Args:
        filename: Name of the Excel file
        row_index: Index of the row to update (0-based)
        updates: Dictionary of column:value pairs to update
        sheet_name: Specific sheet to update (optional)
    
    Returns:
        Dict containing operation result
    """
    filepath = _get_excel_path(filename)
    
    try:
        # Read current data, defaulting to the first sheet if none is specified
        df = pd.read_excel(filepath, sheet_name=sheet_name or 0)
        
        if row_index >= len(df):
            raise IndexError(f"Row index {row_index} out of range. File has {len(df)} rows.")
        
        # Update the row
        for column, value in updates.items():
            if column not in df.columns:
                raise ValueError(f"Column '{column}' not found in Excel file")
            df.at[row_index, column] = value
        
        # Save back to Excel
        if sheet_name:
            # If specific sheet, need to preserve other sheets
            with pd.ExcelWriter(filepath, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
            df.to_excel(filepath, index=False)
        
        _log_operation("UPDATE", filename, f"Updated row {row_index} with {updates}")
        
        return {
            "success": True,
            "filename": filename,
            "row_index": row_index,
            "updates": updates,
            "message": f"Successfully updated row {row_index}"
        }
    
    except Exception as e:
        error_msg = f"Error updating Excel row: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)

def add_excel_row(filename: str, new_data: Dict[str, Any], sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Add a new row to Excel file.
    
    Args:
        filename: Name of the Excel file
        new_data: Dictionary of column:value pairs for new row
        sheet_name: Specific sheet to add to (optional)
    
    Returns:
        Dict containing operation result
    """
    filepath = _get_excel_path(filename)
    
    try:
        # Read current data, defaulting to the first sheet if none is specified
        df = pd.read_excel(filepath, sheet_name=sheet_name or 0)
        
        # Validate columns
        for column in new_data.keys():
            if column not in df.columns:
                raise ValueError(f"Column '{column}' not found in Excel file")
        
        # Create new row with all columns (fill missing with empty values)
        new_row = {}
        for col in df.columns:
            new_row[col] = new_data.get(col, "")
        
        # Add the new row
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Save back to Excel
        if sheet_name:
            # If specific sheet, need to preserve other sheets
            with pd.ExcelWriter(filepath, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
            df.to_excel(filepath, index=False)
        
        _log_operation("ADD", filename, f"Added new row with data: {new_data}")
        
        return {
            "success": True,
            "filename": filename,
            "new_row_index": len(df) - 1,
            "new_data": new_data,
            "message": f"Successfully added new row to {filename}"
        }
    
    except Exception as e:
        error_msg = f"Error adding Excel row: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)

def delete_excel_row(filename: str, row_index: int, sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete a specific row from Excel file.
    
    Args:
        filename: Name of the Excel file
        row_index: Index of the row to delete (0-based)
        sheet_name: Specific sheet to delete from (optional)
    
    Returns:
        Dict containing operation result
    """
    filepath = _get_excel_path(filename)
    
    try:
        # Read current data, defaulting to the first sheet if none is specified
        df = pd.read_excel(filepath, sheet_name=sheet_name or 0)
        
        if row_index >= len(df):
            raise IndexError(f"Row index {row_index} out of range. File has {len(df)} rows.")
        
        # Store the row data for logging
        deleted_row = df.iloc[row_index].to_dict()
        
        # Delete the row
        df = df.drop(df.index[row_index]).reset_index(drop=True)
        
        # Save back to Excel
        if sheet_name:
            # If specific sheet, need to preserve other sheets
            with pd.ExcelWriter(filepath, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
            df.to_excel(filepath, index=False)
        
        _log_operation("DELETE", filename, f"Deleted row {row_index}: {deleted_row}")
        
        return {
            "success": True,
            "filename": filename,
            "deleted_row_index": row_index,
            "deleted_data": deleted_row,
            "message": f"Successfully deleted row {row_index}"
        }
    
    except Exception as e:
        error_msg = f"Error deleting Excel row: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)

def get_excel_info(filename: str) -> Dict[str, Any]:
    """
    Get information about an Excel file structure.
    
    Args:
        filename: Name of the Excel file
    
    Returns:
        Dict containing file structure information
    """
    filepath = _get_excel_path(filename)
    
    try:
        excel_file = pd.ExcelFile(filepath)
        info = {
            "filename": filename,
            "sheets": excel_file.sheet_names,
            "sheet_info": {}
        }
        
        for sheet in excel_file.sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet)
            info["sheet_info"][sheet] = {
                "rows": len(df),
                "columns": df.columns.tolist(),
                "sample_data": df.head(2).to_dict('records') if len(df) > 0 else []
            }
        
        return info
    
    except Exception as e:
        error_msg = f"Error getting Excel info: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg) 