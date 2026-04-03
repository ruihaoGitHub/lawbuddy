# -*- coding: utf-8 -*-
"""
PDF Text Extraction Script

A general-purpose script for extracting text content from PDF files.
Uses pdfplumber for high-quality text extraction with layout preservation.

Usage:
    python extract_text.py <pdf_file> [output_file]

Arguments:
    pdf_file    - Path to the PDF file (required)
    output_file - Path for the output text file (optional)
                  Defaults to <pdf_name>_text.txt in the same directory
"""

import pdfplumber
import sys
import os
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def extract_pdf_text(pdf_path: str, output_path: str | None = None) -> str:
    """
    Extract text from a PDF file and optionally save to a text file.
    
    Args:
        pdf_path: Path to the PDF file
        output_path: Optional path for output text file
    
    Returns:
        The extracted text content
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    if not pdf_path.suffix.lower() == '.pdf':
        raise ValueError(f"File must be a PDF: {pdf_path}")
    
    if output_path is None:
        output_path = pdf_path.parent / f"{pdf_path.stem}_text.txt"
    else:
        output_path = Path(output_path)
    
    full_text = ""
    
    with pdfplumber.open(pdf_path) as pdf:
        full_text += f"PDF File: {pdf_path.name}\n"
        full_text += f"Total Pages: {len(pdf.pages)}\n"
        full_text += f"{'=' * 60}\n\n"
        
        for i, page in enumerate(pdf.pages, 1):
            full_text += f"{'─' * 60}\n"
            full_text += f"Page {i}\n"
            full_text += f"{'─' * 60}\n"
            
            text = page.extract_text()
            if text:
                full_text += text + "\n\n"
            else:
                full_text += "[No text content on this page]\n\n"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    
    return full_text


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_text.py <pdf_file> [output_file]")
        print("\nArguments:")
        print("  pdf_file    - Path to the PDF file (required)")
        print("  output_file - Path for output text file (optional)")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        print(f"Extracting text from: {pdf_path}")
        text = extract_pdf_text(pdf_path, output_path)
        
        if output_path:
            print(f"Text saved to: {output_path}")
        else:
            pdf_path = Path(pdf_path)
            print(f"Text saved to: {pdf_path.parent / f'{pdf_path.stem}_text.txt'}")
        
        print(f"\nExtracted {len(text)} characters.")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
