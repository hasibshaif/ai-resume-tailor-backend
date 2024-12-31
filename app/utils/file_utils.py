import os
import logging


def save_file(file, folder="static/uploads", filename="master_resume.docx"):
    """
    Save an uploaded file to the specified folder with the given filename.
    """
    os.makedirs(folder, exist_ok=True)  # Ensure the folder exists
    filepath = os.path.join(folder, filename)  # Save with a specific filename
    try:
        file.save(filepath)  # Save the file
        logging.info(f"File saved successfully at: {filepath}")
    except Exception as e:
        logging.error(f"Error saving file: {e}")
    return filepath


logging.basicConfig(level=logging.DEBUG)


def extract_docx_structure(file_path):
    """
    Extract text and formatting from a .docx file.
    """
    from docx import Document

    doc = Document(file_path)
    content = []

    for para in doc.paragraphs:
        if not para.runs:  # Skip paragraphs with no runs
            content.append(
                {"text": para.text, "style": para.style.name}
            )  # Basic info for empty runs
            continue

        for run in para.runs:
            content.append(
                {
                    "text": run.text,  # Use run text instead of paragraph text for finer granularity
                    "style": para.style.name,
                    "font_name": run.font.name if run.font and run.font.name else None,
                    "font_size": run.font.size.pt
                    if run.font and run.font.size
                    else None,
                    "bold": run.bold if run else False,
                    "italic": run.italic if run else False,
                    "underline": run.underline if run else False,
                }
            )

    return content
