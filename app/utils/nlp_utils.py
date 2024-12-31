import os
import openai
import tempfile
import requests
from dotenv import load_dotenv
from docx import Document
from docx.shared import RGBColor, Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.section import WD_SECTION
from docx.shared import Twips

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")


def chunk_text(text, max_tokens=1500):
    """
    Chunk text into parts that fit within the token limit.
    """
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        # Add words to the current chunk until it exceeds the max token limit
        if len(" ".join(current_chunk)) + len(word) + 1 > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
        current_chunk.append(word)

    # Add any remaining words as the last chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks


def extract_docx_structure(file_path):
    """
    Extract comprehensive formatting from a .docx file.
    """
    doc = Document(file_path)
    content = []

    # Extract document-level formatting
    doc_props = {
        "section_props": [
            {
                "page_width": section.page_width.twips,
                "page_height": section.page_height.twips,
                "left_margin": section.left_margin.twips,
                "right_margin": section.right_margin.twips,
                "top_margin": section.top_margin.twips,
                "bottom_margin": section.bottom_margin.twips,
                "header_distance": section.header_distance.twips,
                "footer_distance": section.footer_distance.twips,
            }
            for section in doc.sections
        ]
    }

    for para in doc.paragraphs:
        # Get paragraph formatting
        para_format = para.paragraph_format
        para_props = {
            "text": para.text,
            "style": para.style.name,
            "alignment": para_format.alignment if para_format.alignment else None,
            "line_spacing": para_format.line_spacing
            if para_format.line_spacing
            else None,
            "space_before": para_format.space_before.pt
            if para_format.space_before
            else None,
            "space_after": para_format.space_after.pt
            if para_format.space_after
            else None,
            "left_indent": para_format.left_indent.twips
            if para_format.left_indent
            else None,
            "right_indent": para_format.right_indent.twips
            if para_format.right_indent
            else None,
            "first_line_indent": para_format.first_line_indent.twips
            if para_format.first_line_indent
            else None,
            "runs": [],
        }

        # Get detailed run-level formatting
        for run in para.runs:
            run_props = {
                "text": run.text,
                "bold": run.bold,
                "italic": run.italic,
                "underline": run.underline,
                "font_name": run.font.name,
                "font_size": run.font.size.pt if run.font.size else None,
                "color": None,
            }

            # Extract font color
            if run.font.color.rgb:
                color = run.font.color.rgb
                run_props["color"] = {"r": color[0], "g": color[1], "b": color[2]}

            para_props["runs"].append(run_props)

        content.append(para_props)

    return content, doc_props


def apply_formatting(doc, content, doc_props):
    """
    Apply extracted formatting to the new document.
    """
    # Apply document-level formatting
    for idx, section_props in enumerate(doc_props["section_props"]):
        section = doc.sections[idx] if idx < len(doc.sections) else doc.add_section()
        section.page_width = Twips(section_props["page_width"])
        section.page_height = Twips(section_props["page_height"])
        section.left_margin = Twips(section_props["left_margin"])
        section.right_margin = Twips(section_props["right_margin"])
        section.top_margin = Twips(section_props["top_margin"])
        section.bottom_margin = Twips(section_props["bottom_margin"])
        section.header_distance = Twips(section_props["header_distance"])
        section.footer_distance = Twips(section_props["footer_distance"])

    # Clear the document
    for paragraph in doc.paragraphs:
        p = paragraph._element
        p.getparent().remove(p)

    # Apply paragraph and run-level formatting
    for para_props in content:
        paragraph = doc.add_paragraph()

        # Apply paragraph formatting
        pf = paragraph.paragraph_format
        if para_props["alignment"]:
            pf.alignment = para_props["alignment"]
        if para_props["line_spacing"]:
            pf.line_spacing = para_props["line_spacing"]
        if para_props["space_before"]:
            pf.space_before = Pt(para_props["space_before"])
        if para_props["space_after"]:
            pf.space_after = Pt(para_props["space_after"])
        if para_props["left_indent"]:
            pf.left_indent = Twips(para_props["left_indent"])
        if para_props["right_indent"]:
            pf.right_indent = Twips(para_props["right_indent"])
        if para_props["first_line_indent"]:
            pf.first_line_indent = Twips(para_props["first_line_indent"])

        # Apply run-level formatting
        for run_props in para_props["runs"]:
            run = paragraph.add_run(run_props["text"])
            run.bold = run_props["bold"]
            run.italic = run_props["italic"]
            run.underline = run_props["underline"]
            if run_props["font_name"]:
                run.font.name = run_props["font_name"]
            if run_props["font_size"]:
                run.font.size = Pt(run_props["font_size"])
            if run_props["color"]:
                run.font.color.rgb = RGBColor(
                    run_props["color"]["r"],
                    run_props["color"]["g"],
                    run_props["color"]["b"],
                )


def generate_tailored_resume_with_chunking(
    s3_url, job_title, job_description, output_file_path
):
    # Download master resume from S3
    response = requests.get(s3_url)
    if response.status_code != 200:
        raise Exception(f"Failed to download master resume from S3: {response.content}")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
        temp_file.write(response.content)
        local_master_resume_path = temp_file.name

    # Extract content from master resume
    content, doc_props = extract_docx_structure(local_master_resume_path)
    master_text = "\n".join([p["text"] for p in content])
    chunks = chunk_text(master_text)

    tailored_content = []
    for chunk in chunks:
        prompt = f"""
        Tailor the following resume section to align with the specified job title and description:
        Resume Section: {chunk}
        Job Title: {job_title}
        Job Description: {job_description}
        """
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.3,
        )
        tailored_content.append(response["choices"][0]["message"]["content"])

    tailored_doc = Document()
    for para in "\n".join(tailored_content).splitlines():
        if para.strip():
            tailored_doc.add_paragraph(para)
    tailored_doc.save(output_file_path)
