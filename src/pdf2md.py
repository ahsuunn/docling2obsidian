import re
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
)
import os
import torch
# Prevent PyTorch memory fragmentation on small VRAM GPUs
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode, PictureItem
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# 1. Setup base paths
vault_root = Path("/home/malik/Documents/obsidian/Notex")
downloads_dir = Path.home() / "Downloads"

attachments_base_dir = vault_root / "00 Meta" / "Assets" / "attachments"
target_note_dir = vault_root / "03 Knowledge" / "Finance Theory 01"
target_note_dir.mkdir(parents=True, exist_ok=True)

# 2. Pipeline setup
pipeline_options = PdfPipelineOptions()
pipeline_options.generate_picture_images = True
# pipeline_options.do_formula_enrichment = True
pipeline_options.images_scale = 1.0

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)

# 3. Specify list of files to process
files_to_process = [
    "02 Present Value Relations.pdf",
    "03 Fixed Income Securities.pdf",
    "04 Equities.pdf",
    "05 Forward and Futures.pdf",
    "06 Options.pdf",
    "07 Risk and Return.pdf",
    "08 Portfolio Theory.pdf",
    "09 CAPM and APT.pdf",
    "10 Capital Budgeting.pdf",
    "11 Efficient Market.pdf",
]

# 4. Batch Processing Loop
for file_name in files_to_process:
    pdf_path = downloads_dir / file_name

    if not pdf_path.exists():
        print(f"Skipping (file not found): {pdf_path}")
        continue

    doc_name = pdf_path.stem
    print(f"Processing: {doc_name}...")

    # Convert document
    result = converter.convert(pdf_path)
    doc = result.document

    # Create document-specific subfolder
    doc_attachments_dir = attachments_base_dir / doc_name
    doc_attachments_dir.mkdir(parents=True, exist_ok=True)

    # Extract images and store filenames
    saved_image_filenames = []
    image_counter = 0

    for element, _ in doc.iterate_items():
        if isinstance(element, PictureItem):
            image = element.get_image(doc)
            if image:
                image_counter += 1
                filename = f"{doc_name.lower().replace(' ', '_')}_img_{image_counter:03d}.png"
                filepath = doc_attachments_dir / filename
                
                image.save(filepath, format="PNG")
                saved_image_filenames.append(filename)

    # Export to markdown
    markdown_content = doc.export_to_markdown(image_mode=ImageRefMode.REFERENCED)

    # --- MODIFICATION: Use an iterator instead of index counters ---
    image_iter = iter(saved_image_filenames)

    def get_next_wikilink(match):
        try:
            filename = next(image_iter)
            return f"![[{filename}]]"
        except StopIteration:
            return ""  # Fallback if there are more placeholders than images

    # Replace placeholders with sequential WikiLinks
    image_pattern = r"\{image_key\}|<!-- image -->|!\[.*?\]\((?:.*?/)?([^/\)]+\.(?:png|jpg|jpeg))\)"
    clean_markdown = re.sub(image_pattern, get_next_wikilink, markdown_content)

    # Cleanup slide headers and trailing whitespaces
    clean_markdown = re.sub(r"^## (Page|Slide) \d+\n?", "", clean_markdown, flags=re.MULTILINE)
    clean_markdown = re.sub(r"[ \t]+$", "", clean_markdown, flags=re.MULTILINE)

    # Save output markdown note
    output_note = target_note_dir / f"{doc_name}.md"
    with open(output_note, "w", encoding="utf-8") as f:
        f.write(clean_markdown)
        
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    print(f"Successfully generated: {output_note}")
