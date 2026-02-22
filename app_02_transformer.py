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
import csv

from tqdm import tqdm

from config import INPUT_DIR, INPUT_ASSETS_PATH, INPUT_SITE_MAP_CSV, INPUT_ASSETS_MAP_CSV, \
    TRANSFORMED_IGNORED_ELEMENT_SELECTORS, BROKEN_LINKS_MAP, TRANSFORMED_IGNORED_URLS, TRANSFORMED_REMAP_URLS, \
    TRANSFORMED_DIR, TRANSFORMED_ASSETS_DIR, IMPORTER_START_URL, TRANSFORMER_TITLE_ADJUSTER
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
            try:
                if re.search(pattern, url):
                    url = re.sub(pattern, repl, url)
            except Exception as e:
                print(f"Error processing URL: {url} for pattern: {pattern} and replacement: {repl}")
                raise e
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
                asset_subfolder = os.path.dirname(current_md_path.replace(TRANSFORMED_DIR+'/',''))
                dst_abs_path = os.path.join(TRANSFORMED_ASSETS_DIR, asset_subfolder, asset_name)
                rel_path = self.get_relative_path(current_md_path, dst_abs_path)

                src = os.path.join(INPUT_ASSETS_PATH, asset_name)
                os.makedirs(os.path.dirname(dst_abs_path), exist_ok=True)  # Ensure deep structure exists
                if os.path.exists(src):
                    shutil.copy2(src, dst_abs_path)
                    tag[attr] = rel_path
                else:
                    self.report_broken_link(src, dst_abs_path, current_md_path)
            elif link.startswith(IMPORTER_START_URL):
                self.report_broken_link(link, current_md_path, attr)

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

    def get_to_process_entries(self):
        out = []
        for url, entry in tqdm(self.site_map.items(), desc="Collecting pages"):
            if entry.status.name != "DOWNLOADED" or not entry.path:
                continue
            if self.should_ignore_page(url):
                continue
            md_path = self.url_to_md[url]
            out.append((url, entry, md_path))
        return out


    def main(self):
        self.create_build_workspace()
        for url, entry, md_path in tqdm(self.get_to_process_entries(), desc="Processing pages"):
            html_path = os.path.join(INPUT_ASSETS_PATH, entry.path)
            with open(html_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            # Extract <main>
            self.remove_ignored_elements(soup)
            main_elem = soup.find("main")
            if not main_elem:
                continue
            title = TRANSFORMER_TITLE_ADJUSTER(soup.title.string) if soup.title and soup.title.string else ""

            # Remove <h1> if matches title
            for h1 in main_elem.find_all("h1"):
                if h1.get_text(strip=True) == title:
                    h1.decompose()

            # Convert links and assets
            os.makedirs(os.path.dirname(md_path), exist_ok=True)
            main_elem = self.convert_links_and_assets(main_elem, md_path)
            # Markdownify
            markdown_content = md(str(main_elem), heading_style="ATX")
            # Extract title
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

    def __init__(self):
        self.broken_links = []


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

            if ref.startswith(IMPORTER_START_URL):
                self.broken_links.append((md_path, ref))
            # Ignore other external links

            if ref.startswith('http://') or ref.startswith('https://') or ref.startswith('mailto:'):
                continue
            # Ignore data:image assets
            if ref.startswith('data:image'):
                continue
            # Resolve relative to the adjusted file
            ref_path = (md_path.parent / ref).resolve()
            try:
                if not ref_path.exists():
                    self.broken_links.append((md_path, ref))
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

    def save(self, csv_path):
        with open(csv_path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["link", "page", "attr"])
            for row in self.broken_links:
                writer.writerow(row)

    def main(self):
        # Use OUTPUT_DIR/adjusted as default
        processing_errors = self.validate_markdown_dir(TRANSFORMED_DIR)
        if len(self.broken_links) > 0:
            print(f'Found {len(self.broken_links)} broken links')
            self.save(os.path.join(TRANSFORMED_DIR, 'broken_links.csv'))
        else:
            print('No broken links found')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transformer CLI")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["transform", "validate", "test-mapping"],
        help="Command to run"
    )
    args = parser.parse_args()

    transformer = Transformer()
    validator = Validator()

    if args.command == "test-mapping":
        transformer.create_build_workspace()
        for url, entry, md_path in tqdm(transformer.get_to_process_entries()):
            # md_path = md_path.replace('build/transformed/', 'build/transformed-test/')
            os.makedirs(os.path.dirname(md_path), exist_ok=True)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"---\noriginal_url: {url}\nchecksum: {entry.hash}\n---\n\n")

    elif args.command == "transform":
        transformer.main()
    elif args.command == "validate":
        validator.main()
    else:
        transformer.main()
        validator.main()