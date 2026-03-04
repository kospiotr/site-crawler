import argparse
import os
import re
import shutil
import time
import urllib.parse
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm
import os
import re
import sys
from pathlib import Path
import csv
from datetime import datetime
import yaml  # <-- add this import

from tqdm import tqdm

from config import INPUT_DIR, INPUT_ASSETS_PATH, INPUT_SITE_MAP_CSV, INPUT_ASSETS_MAP_CSV, \
    TRANSFORMED_IGNORED_ELEMENT_SELECTORS, BROKEN_LINKS_MAP, TRANSFORMED_IGNORED_URLS, TRANSFORMED_REMAP_URLS, \
    TRANSFORMED_DIR, TRANSFORMED_ASSETS_DIR, IMPORTER_DOMAIN, IMPORTER_START_URL, TRANSFORMER_TITLE_ADJUSTER, \
    TRANSFORMED_BROKEN_LINKS_CSV, FIXED_DIR
from app_01_importer import Sitemap


def backup_file(file_to_backup):
    if os.path.exists(file_to_backup):
        timestamp = int(time.time())
        file_timestamp = int(os.path.getmtime(file_to_backup))
        filename = os.path.splitext(os.path.basename(file_to_backup))[0]
        extension = os.path.splitext(file_to_backup)[1]
        target_file_path = f"{os.path.dirname(file_to_backup)}/{filename}{extension}-{timestamp}.bak"
        shutil.copy(file_to_backup, target_file_path)

class Transformer:

    def __init__(self):
        self.site_map = Sitemap(INPUT_SITE_MAP_CSV, None)
        self.assets_map = Sitemap(INPUT_ASSETS_MAP_CSV, None)
        self.report_from = []
        self.report_to = []

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

        def process_tag(tag, assets, to_decompose):
            attr = "href" if tag.name == "a" else "src"
            link = tag.get(attr)
            if not link:
                return
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
                    asset = assets.get(rel_path, {
                        'tag': tag.name,
                        'attribute': attr,
                        'alt':  tag.get('alt', ''),
                        'title': tag.get('title', ''),
                        'href': tag.get('href', ''),
                        'text': tag.get_text(strip=True)
                    })

                    text = tag.get_text(strip=True)
                    if asset.get('text') != text and text != '':
                        asset['text'] = asset['text'] + ' ' + text

                    assets[rel_path] = asset

            if IMPORTER_DOMAIN in link:
                to_decompose.append(tag)

        assets = {}
        to_decompose = []

        for tag in soup.find_all(["a"]):
            process_tag(tag, assets, to_decompose)

        for tag in to_decompose:
            tag.decompose()

        to_decompose = []
        for tag in soup.find_all(["img", "audio", "video", "source"]):
            process_tag(tag, assets, to_decompose)

        for tag in to_decompose:
            tag.decompose()

        return soup, assets



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
                self.report_from.append((url,None,'broken'))
                continue
            if self.should_ignore_page(url):
                self.report_from.append((url,None,'ignored'))
                continue
            md_path = self.url_to_md[url]
            out.append((url, entry, md_path))
        return out

    def write_report_from(self):
        with open(os.path.join(TRANSFORMED_DIR, 'report_from.csv'), "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["from", "to", "details"])
            for row in self.report_from:
                writer.writerow(row)

    def write_report_to(self):
        with open(os.path.join(TRANSFORMED_DIR, 'report_to.csv'), "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["from", "to", "details"])
            for row in self.report_to:
                writer.writerow(row)

    @staticmethod
    def write_frontmatter(f, frontmatter_obj):
        """
        Write the frontmatter_obj as YAML frontmatter to the file-like object f.
        """
        f.write("---\n")
        yaml.safe_dump(frontmatter_obj, f, allow_unicode=True, sort_keys=False)
        f.write("---\n\n")

    def transform(self):
        self.create_workspace()
        for url, entry, md_path in tqdm(self.get_to_process_entries(), desc="Processing pages"):
            html_path = os.path.join(INPUT_ASSETS_PATH, entry.path)
            with open(html_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            # Extract <main>
            self.remove_ignored_elements(soup)
            main_elem = soup.find("main")
            if not main_elem:
                self.report_from.append((url,None,'no main content'))
                continue

            title = TRANSFORMER_TITLE_ADJUSTER(soup.title.string) if soup.title and soup.title.string else ""

            # Remove <h1> if matches title
            for h1 in main_elem.find_all("h1"):
                if h1.get_text(strip=True) == title:
                    h1.decompose()

            # Convert links and assets
            os.makedirs(os.path.dirname(md_path), exist_ok=True)
            main_elem, assets = self.convert_links_and_assets(main_elem, md_path)
            # Markdownify
            markdown_content = md(str(main_elem), heading_style="ATX")
            # Prepare frontmatter
            frontmatter = {
                "title": title,
                "original_url": url,
                "checksum": entry.hash,
                "assets": assets
            }
            # Extract date from filename if present
            date_match = re.match(r".*(\d{4}-\d{2}-\d{2}).*", url.replace(r'/', '-'))
            date_str = None
            if date_match:
                date_str = date_match.group(1)
                # Optionally validate date
                try:
                    datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    date_str = None
            if date_str:
                frontmatter["date"] = date_str
            # Write adjusted file
            with open(md_path, "w", encoding="utf-8") as f:
                self.write_frontmatter(f, frontmatter)
                f.write(markdown_content)
                self.report_from.append((url,md_path,None))
                self.report_to.append((url,md_path,None))

        self.write_report_from()
        self.write_report_to()

    def create_workspace(self):
        shutil.rmtree(TRANSFORMED_DIR, ignore_errors=True)
        os.makedirs(TRANSFORMED_DIR, exist_ok=True)
        os.makedirs(TRANSFORMED_ASSETS_DIR, exist_ok=True)

    def test_mapping(self):
        self.create_workspace()
        for url, entry, md_path in tqdm(transformer.get_to_process_entries()):
            # md_path = md_path.replace('build/transformed/', 'build/transformed-test/')
            os.makedirs(os.path.dirname(md_path), exist_ok=True)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(f"---\noriginal_url: {url}\nchecksum: {entry.hash}\n---\n\n")
                self.report_from.append((url,md_path,None))
                self.report_to.append((url,md_path,None))
        self.write_report_from()
        self.write_report_to()


class Validator:

    def __init__(self, dir=TRANSFORMED_DIR):
        self.broken_links = []
        self.dir = dir

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
            type = "link" if ref in links else "image"
            if ref.startswith(IMPORTER_START_URL):
                self.broken_links.append((md_path, ref, type))
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
                    self.broken_links.append((md_path, ref, type))
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
        backup_file(csv_path)
        with open(csv_path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["file", "link", "type"])
            for row in self.broken_links:
                writer.writerow(row)

    def validate(self):
        self.broken_links = []
        processing_errors = self.validate_markdown_dir(self.dir)
        if len(processing_errors) > 0:
            print(f'Encountered errors during processing: {processing_errors}')

        self.save(os.path.join(self.dir, 'report_broken_links.csv'))
        if len(self.broken_links) > 0:
            print(f'Found {len(self.broken_links)} broken links')
        else:
            print('No broken links found')

class BrokenLinkFixer:
    def __init__(self, test: bool = False):
        self.broken_links = self.load_broken_links(TRANSFORMED_BROKEN_LINKS_CSV)
        self.test = test

    def create_workspace(self):
        shutil.rmtree(FIXED_DIR, ignore_errors=True)
        os.makedirs(FIXED_DIR, exist_ok=True)

    def load_broken_links(self, csv_path):
        broken = []
        if not os.path.exists(csv_path):
            return broken
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Expect columns: link, page, attr
                broken.append({
                    "file": row.get("file"),
                    "link": row.get("link"),
                    "type": row.get("type")
                })
        return broken

    def fix_file(self, file, links):
        if not self.test:
            backup_file(file)

        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
        for bl in links:
            link_url = bl["link"]
            type = bl["type"]
            if type == "image":
                # Remove image markdown: ![alt](link "optional title")
                # Also remove images inside links: [![](link "title")](...)
                # Remove [![](link "title")](...) first
                content = re.sub(
                    rf'\[!\[.*?\]\(\s*{re.escape(link_url)}(?:\s+"[^"]*")?\s*\)\]\([^\)]*\)',
                    '',
                    content
                )
                # Then remove standalone images
                content = re.sub(
                    rf'!\[.*?\]\(\s*{re.escape(link_url)}(?:\s+"[^"]*")?\s*\)',
                    '',
                    content
                )
            elif type == "link":
                # Replace [text](link) with just text
                content = re.sub(
                    rf'\[([^\]]+)\]\(\s*{re.escape(link_url)}(?:\s+"[^"]*")?\s*\)',
                    r'\1',
                    content
                )
        if self.test:
            file = file.replace(TRANSFORMED_DIR, FIXED_DIR)
            os.makedirs(os.path.dirname(file), exist_ok=True)

        with open(file, "w", encoding="utf-8") as f:
            f.write(content)

    def fix_all(self):
        # Group broken links by page
        links_by_page = {}
        for bl in self.broken_links:
            file = bl["file"]
            links_by_page.setdefault(file, []).append(bl)

        for file, link in tqdm(links_by_page.items(), desc="Fixing broken links"):
            if os.path.exists(file):
                self.fix_file(file, link)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transformer CLI")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["transform", "validate", "test-mapping", "fix-apply", "fix-test"],
        help="Command to run"
    )
    args = parser.parse_args()

    transformer = Transformer()
    transformed_validator = Validator(TRANSFORMED_DIR)
    fixed_validator = Validator(FIXED_DIR)
    fixer = BrokenLinkFixer()

    if args.command == "test-mapping":
        transformer.test_mapping()

    elif args.command == "transform":
        transformer.transform()
    elif args.command == "validate":
        transformed_validator.validate()
    elif args.command == "fix-test":
        fixer = BrokenLinkFixer(test=True)
        transformed_validator.validate()
        fixer.fix_all()
        shutil.copytree(TRANSFORMED_ASSETS_DIR, os.path.join(FIXED_DIR, 'assets'))
        fixed_validator.validate()
    elif args.command == "fix-apply":
        transformed_validator.validate()
        fixer.fix_all()
        transformed_validator.validate()
    else:
        transformer.transform()
        transformed_validator.validate()
        fixer.fix_all()
        transformed_validator.validate()