from docx import Document


def extract_text_with_formatting(docx_path: str) -> str:
    """
    Extract text and formatting (font size, bold, etc.) from a Word document (.docx).
    """
    doc = Document(docx_path)
    formatted_text = ""

    for para in doc.paragraphs:
        for run in para.runs:  # Each run is a piece of text with a consistent style
            font_size = run.font.size
            text = run.text
            is_bold = run.bold
            formatted_text += f"[Font Size: {font_size}, Bold: {is_bold}] {text}\n"

    return formatted_text
