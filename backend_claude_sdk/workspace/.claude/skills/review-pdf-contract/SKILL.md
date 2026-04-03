---
name: review-pdf-contract
description: Use this skill when the user wants you to help review review a contract from PDF files. This skill extracts the content of a pdf as text, which can be used for further analysis or processing.
---

# PDF Contract Review Skill

Review the content from PDF files using pdfplumber for high-quality text extraction with layout preservation.

## When to Use This Skill

Use this skill when you need to:
- Review a contract from a PDF document
- Read and analyze PDF content
- Convert PDF to plain text
- Save PDF text to a file for further processing

## Usage

### Basic Text Extraction

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

### Extract with Page Numbers

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages, 1):
        print(f"=== Page {i} ===")
        text = page.extract_text()
        if text:
            print(text)
        else:
            print("[No text content on this page]")
```

### Save Extracted Text to File

```python
import pdfplumber

def extract_pdf_to_file(pdf_path, output_path):
    with pdfplumber.open(pdf_path) as pdf:
        full_text = f"PDF: {pdf_path}\n"
        full_text += f"Total Pages: {len(pdf.pages)}\n\n"
        
        for i, page in enumerate(pdf.pages, 1):
            full_text += f"{'='*50}\n"
            full_text += f"Page {i}\n"
            full_text += f"{'='*50}\n"
            text = page.extract_text()
            if text:
                full_text += text + "\n\n"
            else:
                full_text += "[No text content]\n\n"
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)
    
    return output_path
```

### the way to construct your review opinion
list all the pros and cons of the contract, and then give your opinion on the contract.
example:
pros:
1. ...
2. ...
...
cons:
1. ...
2. ...
...
opinion:
...
**be concise about pros and give more details about cons**

## Script: extract_text.py

A ready-to-use script for extracting text from PDFs:

```bash
python .claude/skills/extract-pdf-text/scripts/extract_text.py <pdf_file> [output_file]
```

**Arguments:**
- `pdf_file`: Path to the PDF file (required)
- `output_file`: Path for the output text file (optional, defaults to `<pdf_name>_text.txt`)

**Examples:**
```bash
# Extract to default output file
python .claude/skills/extract-pdf-text/scripts/extract_text.py contract.pdf

# Extract to specific output file
python .claude/skills/extract-pdf-text/scripts/extract_text.py contract.pdf contract_content.txt
```

## Supported File Types

- `.pdf` - Standard PDF documents
- Text-based PDFs (not scanned images)
- PDFs with embedded fonts

## Limitations

- Scanned PDFs require OCR (use the `pdf` skill instead)
- Complex layouts may not preserve exact formatting
- Tables are extracted as text, not structured data

## Dependencies

```bash
pip install pdfplumber
```

