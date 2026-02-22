import pypdf

pdf_path = r"c:\projeto\keyAccess\Demonstracao de Caso de Uso - LG_V3.pdf"

try:
    reader = pypdf.PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    
    # Save text to a file for analysis
    with open("pdf_content.txt", "w", encoding="utf-8") as f:
        f.write(text)
        
    print("PDF content extracted to pdf_content.txt")
    print(text[:500]) # Print first 500 chars to verify
except Exception as e:
    print(f"Error reading PDF: {e}")
