from docx import Document
import os


def generate_docx(tailored_resume: str, output_folder="static/uploads"):
    """
    Generates a .docx file from the tailored resume text.
    """
    # Ensure the output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Define the filename for the Word document
    filename = f"Tailored_Resume.docx"
    file_path = os.path.join(output_folder, filename)

    # Create a new Word document
    doc = Document()

    # Add the tailored resume content to the document
    doc.add_paragraph(tailored_resume)

    # Save the document
    doc.save(file_path)

    return file_path  # Return the file path to the generated .docx file
