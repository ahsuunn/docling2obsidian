import os
import re
import subprocess
from pathlib import Path
import torch

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode, PictureItem

# Prevent PyTorch memory fragmentation on small VRAM GPUs
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# 1. Setup base paths
vault_root = Path("/home/malik/Documents/obsidian/Notex")
downloads_dir = Path.home() / "Documents" / "obsidian" / "Notex" / "00 Meta" / "Assets" / "pdfs" / "Financial Management"

attachments_base_dir = vault_root / "00 Meta" / "Assets" / "attachments"
target_note_dir = vault_root / "01 Academics" / "7th Semester (2026-1)" / "Financial Management"
target_note_dir.mkdir(parents=True, exist_ok=True)

# 2. Pipeline setup with explicit image scaling and formula enrichment
pipeline_options = PdfPipelineOptions()
pipeline_options.generate_picture_images = True
pipeline_options.do_formula_enrichment = True
pipeline_options.images_scale = 1.0

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)

# 3. List of presentation files to process (PPT and PPTX only)
files_to_process = [
    "ch01.pptx",
    "ch02.pptx",
    "ch03.pptx",
    "ch04.ppt",
    "ch05.pptx",
    "ch06.pptx",
]


def ensure_pptx(file_path: Path) -> Path:
    """Convert legacy binary .ppt to .pptx via LibreOffice if needed for Docling."""
    if file_path.suffix.lower() == ".ppt":
        pptx_path = file_path.with_suffix(".pptx")
        if not pptx_path.exists():
            print(f"Converting legacy PPT to PPTX for Docling compatibility: {file_path.name}...")
            try:
                subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "pptx", str(file_path), "--outdir", str(file_path.parent)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                print(f"LibreOffice conversion fallback failed: {e}")
                return file_path
        return pptx_path
    return file_path


# 4. Batch Processing Loop
for file_name in files_to_process:
    raw_path = downloads_dir / file_name

    if not raw_path.exists():
        print(f"Skipping (file not found): {raw_path}")
        continue

    input_path = ensure_pptx(raw_path)
    doc_name = raw_path.stem
    print(f"Processing: {input_path.name}...")

    try:
        result = converter.convert(input_path)
        doc = result.document

        # Create document-specific subfolder in attachments
        doc_attachments_dir = attachments_base_dir / doc_name
        doc_attachments_dir.mkdir(parents=True, exist_ok=True)

        # Image Extraction (Iterates over all PictureItem elements)
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

        # Export raw markdown
        markdown_content = doc.export_to_markdown(image_mode=ImageRefMode.REFERENCED)

        # Sequential replacement of image tags with Obsidian WikiLinks
        image_iter = iter(saved_image_filenames)

        def get_next_wikilink(match):
            try:
                filename = next(image_iter)
                return f"![[{filename}]]"
            except StopIteration:
                return ""

        image_pattern = r"\{image_key\}|<!-- image -->|!\[.*?\]\((?:.*?/)?([^/\)]+\.(?:png|jpg|jpeg))\)"
        clean_markdown = re.sub(image_pattern, get_next_wikilink, markdown_content)

        # Clean slide headings & trailing spaces
        clean_markdown = re.sub(r"^## (Page|Slide) \d+\n?", "", clean_markdown, flags=re.MULTILINE)
        clean_markdown = re.sub(r"[ \t]+$", "", clean_markdown, flags=re.MULTILINE)

        output_note = target_note_dir / f"{doc_name}.md"
        with open(output_note, "w", encoding="utf-8") as f:
            f.write(clean_markdown)

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        print(f"Successfully generated: {output_note}")

    except Exception as e:
        print(f"Error processing {file_name}: {e}")
