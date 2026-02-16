import os
import re
import sys
from pathlib import Path

from tqdm import tqdm

from config import OUTPUT_DIR

def extract_links_and_assets(md_content):
    # Markdown links: [text](url "optional title")
    link_pattern = re.compile(r'\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)')
    # Markdown images: ![alt](url "optional title")
    image_pattern = re.compile(r'!\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)')
    links = link_pattern.findall(md_content)
    images = image_pattern.findall(md_content)
    # Remove images from links (since images are also links)
    links = [l for l in links if l not in images]
    return links, images

def validate_markdown_file(md_path, base_dir):
    errors = []
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    links, images = extract_links_and_assets(content)
    all_refs = links + images
    for ref in all_refs:
        # Ignore external links
        if ref.startswith('http://') or ref.startswith('https://') or ref.startswith('mailto:'):
            continue
        # Ignore data:image assets
        if ref.startswith('data:image'):
            continue
        # Resolve relative to the markdown file
        ref_path = (md_path.parent / ref).resolve()
        try:
            if not ref_path.exists():
                errors.append(f"Broken reference in {md_path}: {ref}")
        except Exception as e:
            errors.append(f"Could not process file {md_path}: {ref}")
    return errors

def validate_markdown_dir(markdown_dir):
    all_errors = []
    for root, dirs, files in tqdm(os.walk(markdown_dir), desc="Validating markdown files"):
        for file in files:
            if file.endswith('.md'):
                md_path = Path(root) / file
                errors = validate_markdown_file(md_path, markdown_dir)
                all_errors.extend(errors)
    return all_errors

def main():
    # Use OUTPUT_DIR/markdown as default
    default_markdown_dir = os.path.join(OUTPUT_DIR, "markdown")
    markdown_dir = sys.argv[1] if len(sys.argv) > 1 else default_markdown_dir
    errors = validate_markdown_dir(markdown_dir)
    if errors:
        print(f"Validation failed. Broken links or missing assets found: {len(errors)}")
        for err in errors:
            print(err)
        sys.exit(2)
    else:
        print("All markdown files are valid. No broken links or missing assets.")

if __name__ == "__main__":
    main()
