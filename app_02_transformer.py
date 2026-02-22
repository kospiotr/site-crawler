import argparse
import os
import re
import shutil
import urllib.parse
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm
import os
import re
import sys
from pathlib import Path

from tqdm import tqdm

from config import INPUT_DIR, INPUT_ASSETS_PATH, INPUT_SITE_MAP_CSV, INPUT_ASSETS_MAP_CSV, \
    TRANSFORMED_IGNORED_ELEMENT_SELECTORS, BROKEN_LINKS_MAP, TRANSFORMED_IGNORED_URLS, TRANSFORMED_REMAP_URLS, \
    TRANSFORMED_DIR, TRANSFORMED_ASSETS_DIR
from app_01_importer import Sitemap



class Transformer:

    def __init__(self):
        self.site_map = Sitemap(INPUT_SITE_MAP_CSV, None)
        self.assets_map = Sitemap(INPUT_ASSETS_MAP_CSV, None)

        self.url_to_md = {}
        for url, entry in tqdm(self.site_map.items(), desc="Building url to md map"):
            if entry.status.name == "DOWNLOADED" and entry.path:
                self.url_to_md[url] = self.url_to_md_path(url, base_dir=TRANSFORMED_DIR)
        self.asset_to_local = {}
        for url, entry in tqdm(self.assets_map.items(), desc="Building asset to local map"):
            if entry.status.name == "DOWNLOADED" and entry.path:
                self.asset_to_local[url] = entry.path

    @staticmethod
    def remap_url(url):
        for pattern, repl in TRANSFORMED_REMAP_URLS.items():
            if re.search(pattern, url):
                return re.sub(pattern, repl, url)
        return url

    def url_to_md_path(self, url, base_dir=TRANSFORMED_DIR):
        url = self.remap_url(url)
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip('/')
        if path.startswith('/'):
            path = path[1:]
        path = os.path.splitext(path)[0] + '.md'
        safe_path = os.path.normpath(path)
        return os.path.join(base_dir, safe_path)

    @staticmethod
    def get_relative_path(from_path, to_path):
        return os.path.relpath(to_path, os.path.dirname(from_path))

    @staticmethod
    def fix_broken_link(link):
        for broken, fixed in BROKEN_LINKS_MAP.items():
            if broken in link:
                link = link.replace(broken, fixed)
        return link

    def convert_links_and_assets(self, soup, current_md_path):
        # Convert <a> and <img> and other asset links to local
        for tag in soup.find_all(["a", "img", "audio", "video", "source"]):
            attr = "href" if tag.name == "a" else "src"
            link = tag.get(attr)
            if not link:
                continue
            # Fix broken links using BROKEN_LINKS_MAP
            link = self.fix_broken_link(link)
            # Convert page links
            if link in self.url_to_md:
                rel_path = self.get_relative_path(current_md_path, self.url_to_md[link])
                tag[attr] = rel_path
            # Convert asset links
            elif link in self.asset_to_local:
                asset_name = self.asset_to_local[link]
                asset_abs_path = os.path.join(TRANSFORMED_DIR, asset_name)
                rel_path = self.get_relative_path(current_md_path, asset_abs_path)
                tag[attr] = rel_path
                src = os.path.join(INPUT_ASSETS_PATH, asset_name)
                dst = os.path.join(TRANSFORMED_ASSETS_DIR, asset_name)
                os.makedirs(os.path.dirname(dst), exist_ok=True)  # Ensure deep structure exists
                if os.path.exists(src):
                    shutil.copy2(src, dst)
        return soup



    @staticmethod
    def remove_ignored_elements(soup: BeautifulSoup):
        for selector in TRANSFORMED_IGNORED_ELEMENT_SELECTORS:
            for el in soup.select(selector):
                el.decompose()

    @staticmethod
    def should_ignore_page(url):
        for pattern in TRANSFORMED_IGNORED_URLS:
            if re.search(pattern, url):
                return True
        return False

    def main(self):
        self.create_build_workspace()

        print('Process each downloaded page')
        for url, entry in tqdm(self.site_map.items(), desc="Processing pages"):
            if entry.status.name != "DOWNLOADED" or not entry.path:
                continue
            if self.should_ignore_page(url):
                continue
            html_path = os.path.join(INPUT_ASSETS_PATH, entry.path)
            with open(html_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            # Extract <main>
            self.remove_ignored_elements(soup)
            main_elem = soup.find("main")
            if not main_elem:
                continue
            # Convert links and assets
            md_path = self.url_to_md[url]
            os.makedirs(os.path.dirname(md_path), exist_ok=True)
            main_elem = self.convert_links_and_assets(main_elem, md_path)
            # Markdownify
            markdown_content = md(str(main_elem), heading_style="ATX")
            # Extract title
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            # Header
            header = f"---\ntitle: {title}\noriginal_url: {url}\nchecksum: {entry.hash}\n---\n\n"
            # Write adjusted file
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(header)
                f.write(markdown_content)

    def create_build_workspace(self):
        shutil.rmtree(TRANSFORMED_DIR, ignore_errors=True)
        os.makedirs(TRANSFORMED_DIR, exist_ok=True)
        os.makedirs(TRANSFORMED_ASSETS_DIR, exist_ok=True)


class Validator:

    def extract_links_and_assets(self, md_content):
        # Markdown links: [text](url "optional title")
        link_pattern = re.compile(r'\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)')
        # Markdown images: ![alt](url "optional title")
        image_pattern = re.compile(r'!\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)')
        links = link_pattern.findall(md_content)
        images = image_pattern.findall(md_content)
        # Remove images from links (since images are also links)
        links = [l for l in links if l not in images]
        return links, images

    def validate_markdown_file(self,md_path, base_dir):
        errors = []
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        links, images = self.extract_links_and_assets(content)
        all_refs = links + images
        for ref in all_refs:
            # Ignore external links
            if ref.startswith('http://') or ref.startswith('https://') or ref.startswith('mailto:'):
                continue
            # Ignore data:image assets
            if ref.startswith('data:image'):
                continue
            # Resolve relative to the adjusted file
            ref_path = (md_path.parent / ref).resolve()
            try:
                if not ref_path.exists():
                    errors.append(f"Broken reference in {md_path}: {ref}")
            except Exception as e:
                errors.append(f"Could not process file {md_path}: {ref}")
        return errors

    def validate_markdown_dir(self,markdown_dir):
        all_errors = []
        for root, dirs, files in tqdm(os.walk(markdown_dir), desc="Validating adjusted files"):
            for file in files:
                if file.endswith('.md'):
                    md_path = Path(root) / file
                    errors = self.validate_markdown_file(md_path, markdown_dir)
                    all_errors.extend(errors)
        return all_errors

    def main(self):
        # Use OUTPUT_DIR/adjusted as default
        default_markdown_dir = os.path.join(INPUT_DIR, "adjusted")
        markdown_dir = sys.argv[1] if len(sys.argv) > 1 else default_markdown_dir
        errors = self.validate_markdown_dir(markdown_dir)
        if errors:
            print(f"Validation failed. Broken links or missing assets found: {len(errors)}")
            for err in errors:
                print(err)
            sys.exit(2)
        else:
            print("All adjusted files are valid. No broken links or missing assets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transformer CLI")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["transform", "validate"],
        help="Command to run"
    )
    args = parser.parse_args()

    importer = Transformer()
    validator = Validator()
    if args.command == "transform":
        importer.main()
    elif args.command == "validate":
        validator.main()
    else:
        importer.main()
        validator.main()