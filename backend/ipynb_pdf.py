"""Convert Jupyter notebooks to PDF using nbconvert.

For each .ipynb in input/ (or a file passed as an argument), shells out to
`jupyter nbconvert --to pdf` and writes the result to output/.
"""

import os
import sys
import subprocess
from pathlib import Path


def convert_notebook_to_pdf(notebook_path: str, output_path: str | None = None) -> bool:
    """
    Args:
        notebook_path (str): Path to the .ipynb file (relative to input folder)
        output_path (str, optional): Output PDF filename. If None, uses same name as notebook
    
    Returns:
        bool: True if conversion successful, False otherwise
    """
    # Early guard: if the provided path is already a PDF, stop
    try:
        if Path(notebook_path).suffix.lower() == ".pdf":
            print("That file is already in pdf format")
            return False
    except Exception:
        pass

    # Set up input and output directories relative to this script
    script_dir = Path(__file__).resolve().parent
    input_dir = script_dir / "input"
    output_dir = script_dir / "output"
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)
    
    # Build full input path
    if os.path.isabs(notebook_path):
        full_input_path = notebook_path
    else:
        full_input_path = input_dir / notebook_path
    
    # Check if notebook file exists
    if not os.path.exists(full_input_path):
        print(f"Error: Notebook file '{full_input_path}' not found")
        return False
    
    # Set output path if not provided
    if output_path is None:
        notebook_name = Path(notebook_path).stem
        output_path = f"{notebook_name}.pdf"
    
    # Build full output path
    full_output_path = output_dir / output_path
    
    try:
        # Use nbconvert to convert notebook to PDF
        cmd = [
            "jupyter", "nbconvert", 
            "--to", "pdf",
            "--output", output_path,
            "--output-dir", str(output_dir),
            str(full_input_path)
        ]
        
        existed_before = os.path.exists(full_output_path)
        print(f"Converting {Path(full_input_path).name} to pdf")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Converted {Path(full_input_path).name} to {full_output_path.name}")
            if existed_before:
                print(f"Overwrote existing file: {full_output_path.name}")
            return True
        else:
            print(f"Conversion failed: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("Error: jupyter nbconvert not found. Make sure Jupyter is installed.")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def main():
    """Main function to handle command line usage"""
    if len(sys.argv) < 2:
        # No args: convert all .ipynb files in input/
        script_dir = Path(__file__).resolve().parent
        input_dir = script_dir / "input"
        notebooks = sorted(p for p in input_dir.glob("*.ipynb"))
        if not notebooks:
            print("No .ipynb files found in input folder")
            print("Usage: python ipynb_pdf.py <notebook_file> [output_file]")
            print("Example: python ipynb_pdf.py my_notebook.ipynb")
            print("Example: python ipynb_pdf.py my_notebook.ipynb output.pdf")
            return
        any_failed = False
        for nb_path in notebooks:
            ok = convert_notebook_to_pdf(nb_path.name, None)
            if not ok:
                any_failed = True
        if any_failed:
            sys.exit(1)
        return
    else:
        notebook_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_notebook_to_pdf(notebook_file, output_file)


if __name__ == "__main__":
    main()
