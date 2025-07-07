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
    """Updates a specific row in an Excel file."""
    filepath = _get_excel_path(filename)
    if not filepath:
        return {"error": f"File not found in the 'pdfs'directory: {filename}"}

    try:
        # Atomically read all sheets, modify, and write back
        xls = pd.read_excel(filepath, sheet_name=None, dtype=str)

        target_sheet = sheet_name or list(xls.keys())[0]
        if target_sheet not in xls:
            return {"error": f"Sheet '{target_sheet}' not found in '{filename}'."}

        df = xls[target_sheet]
        df.fillna("", inplace=True)

        if row_index < 0 or row_index >= len(df):
            return {"error": f"Row index {row_index} is out of bounds."}

        for col, value in updates.items():
            if col in df.columns:
                df.loc[row_index, col] = str(value)
            else:
                return {"error": f"Column '{col}' not found in {filename}."}
        
        xls[target_sheet] = df

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for s_name, s_df in xls.items():
                s_df.to_excel(writer, sheet_name=s_name, index=False)

        return {"message": f"Row {row_index} updated successfully."}

    except Exception as e:
        return {"error": f"Failed to update row: {str(e)}"}


def add_excel_row(filename: str, new_data: Dict[str, Any], sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """Adds a new row to an Excel file."""
    filepath = _get_excel_path(filename)
    if not filepath:
        return {"error": f"File not found in the 'pdfs' directory: {filename}"}

    try:
        # Atomically read all sheets, modify, and write back
        xls = pd.read_excel(filepath, sheet_name=None, dtype=str)
        
        target_sheet = sheet_name or list(xls.keys())[0]
        if target_sheet not in xls:
            return {"error": f"Sheet '{target_sheet}' not found in '{filename}'."}
            
        df = xls[target_sheet]
        df.fillna("", inplace=True)

        new_row_data = {col: str(new_data.get(col, "")) for col in df.columns}
        
        # Use pandas.concat instead of df.loc to append the new row
        new_row_df = pd.DataFrame([new_row_data])
        df = pd.concat([df, new_row_df], ignore_index=True)

        xls[target_sheet] = df

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for s_name, s_df in xls.items():
                s_df.to_excel(writer, sheet_name=s_name, index=False)

        return {"message": "Row added successfully."}

    except Exception as e:
        return {"error": f"Failed to add row: {str(e)}"}


def delete_excel_row(filename: str, row_index: int, sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a specific row from an Excel file."""
    filepath = _get_excel_path(filename)
    if not filepath:
        return {"error": f"File not found in the 'pdfs' directory: {filename}"}

    try:
        # Atomically read all sheets, modify, and write back
        xls = pd.read_excel(filepath, sheet_name=None, dtype=str)

        target_sheet = sheet_name or list(xls.keys())[0]
        if target_sheet not in xls:
            return {"error": f"Sheet '{target_sheet}' not found in '{filename}'."}

        df = xls[target_sheet]
        df.fillna("", inplace=True)

        if row_index < 0 or row_index >= len(df):
            return {"error": f"Row index {row_index} is out of bounds."}

        deleted_row_data = df.loc[row_index].to_dict()
        df = df.drop(index=row_index).reset_index(drop=True)
        
        xls[target_sheet] = df

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for s_name, s_df in xls.items():
                s_df.to_excel(writer, sheet_name=s_name, index=False)

        return {"message": f"Row {row_index} deleted successfully."}

    except Exception as e:
        return {"error": f"Failed to delete row: {str(e)}"}

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