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
        return {"error": f"File not found in the 'pdfs' directory: {filename}"}

    try:
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

    except PermissionError:
        return {"error": f"Could not modify '{filename}' due to a permission error. Please ensure the file is not open in another program."}
    except Exception as e:
        return {"error": f"An unexpected error occurred while updating a row: {str(e)}"}


def add_excel_row(filename: str, new_data: Dict[str, Any], sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """Adds a new row to an Excel file."""
    filepath = _get_excel_path(filename)
    if not filepath:
        return {"error": f"File not found in the 'pdfs' directory: {filename}"}

    try:
        xls = pd.read_excel(filepath, sheet_name=None, dtype=str)
        target_sheet = sheet_name or list(xls.keys())[0]
        if target_sheet not in xls:
            return {"error": f"Sheet '{target_sheet}' not found in '{filename}'."}
            
        df = xls[target_sheet]
        df.fillna("", inplace=True)

        new_row_data = {col: "" for col in df.columns}
        for key, value in new_data.items():
            if key in new_row_data:
                new_row_data[key] = str(value)
        
        new_row_df = pd.DataFrame([new_row_data])
        df = pd.concat([df, new_row_df], ignore_index=True)
        xls[target_sheet] = df

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for s_name, s_df in xls.items():
                s_df.to_excel(writer, sheet_name=s_name, index=False)

        return {"message": "Row added successfully."}

    except PermissionError:
        return {"error": f"Could not modify '{filename}' due to a permission error. Please ensure the file is not open in another program."}
    except Exception as e:
        return {"error": f"An unexpected error occurred while adding a row: {str(e)}"}


def delete_excel_row(filename: str, row_index: int, sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a specific row from an Excel file by row index."""
    filepath = _get_excel_path(filename)
    if not filepath:
        return {"error": f"File not found in the 'pdfs' directory: {filename}"}

    try:
        xls = pd.read_excel(filepath, sheet_name=None, dtype=str)
        target_sheet = sheet_name or list(xls.keys())[0]
        if target_sheet not in xls:
            return {"error": f"Sheet '{target_sheet}' not found in '{filename}'."}

        df = xls[target_sheet]
        df.fillna("", inplace=True)

        if row_index < 0 or row_index >= len(df):
            return {"error": f"Row index {row_index} is out of bounds."}

        df = df.drop(index=row_index).reset_index(drop=True)
        xls[target_sheet] = df

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for s_name, s_df in xls.items():
                s_df.to_excel(writer, sheet_name=s_name, index=False)

        return {"message": f"Row {row_index} deleted successfully."}

    except PermissionError:
        return {"error": f"Could not modify '{filename}' due to a permission error. Please ensure the file is not open in another program."}
    except Exception as e:
        return {"error": f"An unexpected error occurred while deleting a row: {str(e)}"}


def delete_excel_record_by_criteria(filename: str, criteria: Dict[str, Any], sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """Deletes records from an Excel file based on matching criteria (e.g., name, account number, etc.)."""
    filepath = _get_excel_path(filename)
    if not filepath:
        return {"error": f"File not found in the 'pdfs' directory: {filename}"}

    try:
        xls = pd.read_excel(filepath, sheet_name=None, dtype=str)
        target_sheet = sheet_name or list(xls.keys())[0]
        if target_sheet not in xls:
            return {"error": f"Sheet '{target_sheet}' not found in '{filename}'."}

        df = xls[target_sheet]
        df.fillna("", inplace=True)

        # Find matching rows based on criteria
        mask = pd.Series([True] * len(df))
        matched_info = []
        
        for column, value in criteria.items():
            if column in df.columns:
                # Convert both to strings for comparison and handle case-insensitive matching
                column_mask = df[column].astype(str).str.lower() == str(value).lower()
                mask = mask & column_mask
            else:
                return {"error": f"Column '{column}' not found in {filename}."}
        
        matching_rows = df[mask]
        
        if len(matching_rows) == 0:
            return {"error": f"No records found matching the criteria: {criteria}"}
        
        # Store info about what we're deleting
        for idx, row in matching_rows.iterrows():
            matched_info.append({
                "row_index": idx,
                "data": row.to_dict()
            })
        
        # Delete the matching rows
        df = df[~mask].reset_index(drop=True)
        xls[target_sheet] = df

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for s_name, s_df in xls.items():
                s_df.to_excel(writer, sheet_name=s_name, index=False)

        return {
            "message": f"Successfully deleted {len(matching_rows)} record(s) matching criteria: {criteria}",
            "deleted_records": matched_info
        }

    except PermissionError:
        return {"error": f"Could not modify '{filename}' due to a permission error. Please ensure the file is not open in another program."}
    except Exception as e:
        return {"error": f"An unexpected error occurred while deleting records: {str(e)}"}

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