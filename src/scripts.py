import re
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode, PictureItem

# 1. Setup base paths
vault_root = Path("/home/malik/Documents/obsidian/Notex")
attachments_base_dir = vault_root / "00 Meta" / "Assets" / "attachments"

target_note_dir = vault_root / "01 Academics" / "7th Semester (2026-1)" / "Big Data"
target_note_dir.mkdir(parents=True, exist_ok=True)

# 2. Pipeline setup
pipeline_options = PdfPipelineOptions()
pipeline_options.generate_picture_images = True
pipeline_options.images_scale = 2.0

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)

# 3. Convert document
doc_name = "04 Apache Hadoop_rev"
pdf_path = f"{doc_name}.pdf"
result = converter.convert(pdf_path)
doc = result.document

# --- MODIFICATION: Create document-specific subfolder under attachments ---
doc_attachments_dir = attachments_base_dir / doc_name
doc_attachments_dir.mkdir(parents=True, exist_ok=True)

# 4. Extract images and store filenames sequentially in a queue
saved_image_filenames = []
image_counter = 0

for element, _ in doc.iterate_items():
    if isinstance(element, PictureItem):
        image = element.get_image(doc)
        if image:
            image_counter += 1
            filename = f"{doc_name.lower().replace(' ', '_')}_img_{image_counter:03d}.png"
            
            # Save PIL image into the document subfolder
            filepath = doc_attachments_dir / filename
            image.save(filepath, format="PNG")
            
            saved_image_filenames.append(filename)

# 5. Export document
markdown_content = doc.export_to_markdown(image_mode=ImageRefMode.REFERENCED)

# 6. Sequential replacement iterator
image_index = 0

def get_next_wikilink(match):
    global image_index
    if image_index < len(saved_image_filenames):
        filename = saved_image_filenames[image_index]
        image_index += 1
        # Obsidian short WikiLinks resolve automatically across subfolders
        return f"![[{filename}]]"
    return ""  # If there are more placeholders than saved images

# Replace {image_key}, <!-- image -->, or standard Markdown image links sequentially
image_pattern = r"\{image_key\}|<!-- image -->|!\[.*?\]\((?:.*?/)?([^/\)]+\.(?:png|jpg|jpeg))\)"
clean_markdown = re.sub(image_pattern, get_next_wikilink, markdown_content)

# 7. Cleanup slide headers and trailing whitespaces
clean_markdown = re.sub(r"^## (Page|Slide) \d+\n?", "", clean_markdown, flags=re.MULTILINE)
clean_markdown = re.sub(r"[ \t]+$", "", clean_markdown, flags=re.MULTILINE)

# Save output
with open(target_note_dir / f"{doc_name}.md", "w", encoding="utf-8") as f:
    f.write(clean_markdown)
