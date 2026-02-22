import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from tqdm import tqdm
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import *
from config import IMPORTER_ASSETS_EXTENSIONS
import csv
import os
from dataclasses import dataclass
from enum import Enum
from rich.live import Live
from rich.table import Table
import copy
import argparse

class Status(Enum):
    NEW = "new"
    DOWNLOADED = "downloaded"
    IGNORED = "ignored"
    ERROR = "error"

@dataclass
class SitemapEntry:
    status: Status = None
    hash: str = None
    path: str = None
    mimetype: str = None
    error: str = None

class Sitemap(dict[str, SitemapEntry]):

    file_path: str = None

    def __init__(self, file_path: str, start_url: str):
        super().__init__()
        self.file_path = file_path

        self.load()
        if not self:
            self.add_new(start_url)

    def load(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row["url"]
                    status = Status(row.get("status"))
                    hash = row.get("hash")
                    path = row.get("path")
                    mimetype = row.get("mimetype", "")
                    error = row.get("error", "")
                    self[url] = SitemapEntry(status, hash, path, mimetype, error)
        return self

    def persist(self):
        with open(self.file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["url", "status", "hash", "path", "mimetype", "error"])
            writer.writeheader()
            for url, data in self.items():
                writer.writerow({
                    "url": url,
                    "status": data.status.value,
                    "hash": data.hash,
                    "path": data.path,
                    "mimetype": data.mimetype,
                    "error": data.error
                })

    def print_summary(self):
        with Live(refresh_per_second=4) as live:
            table = Table()
            table.add_column("Metric")
            table.add_column("Value")

            summary = {}
            for entry in self.values():
                summary[entry.status] = summary.get(entry.status, 0) + 1
            for status, count in summary.items():
                table.add_row(str(status).capitalize(), f"{count}")

            live.update(table)

    def add_new(self, url, persist=True):
        self[url] = SitemapEntry(Status.NEW)
        if persist:
            self.persist()

    def add_downloaded(self, url: str, hash: str, path: str, mimetype: str):
        self[url] = SitemapEntry(Status.DOWNLOADED, hash, path, mimetype)
        self.persist()

    def add_ignored(self, url):
        self[url] = SitemapEntry(Status.IGNORED)
        self.persist()

    def add_error(self, url: str, e: Exception):
        self[url] = SitemapEntry(Status.ERROR, error=str(e))
        self.persist()

    def copy_entry(self, from_url: str, to_url: str):
        existing_entry: SitemapEntry = copy.copy(self[from_url])
        self[to_url] = existing_entry
        self.persist()

    def get_new_entries(self):
        return [url for url, entry in self.items() if entry.status == Status.NEW]

    def get_downloaded_entries(self):
        return [(url, entry) for url, entry in self.items() if entry.status == Status.DOWNLOADED]

class Importer:

    def __init__(self):
        for d in [INPUT_ASSETS_PATH]:
            os.makedirs(d, exist_ok=True)
        self.visited = set()
        self.domain = urlparse(IMPORTER_START_URL).netloc
        self.site_map = Sitemap(INPUT_SITE_MAP_CSV, IMPORTER_START_URL)
        self.assets_map = Sitemap(INPUT_ASSETS_MAP_CSV, IMPORTER_START_URL)

    def is_internal(self, url: str) -> bool:
        return urlparse(url).netloc in ("", self.domain)

    @staticmethod
    def get_checksum(html: str) -> str:
        return hashlib.sha256(html.encode("utf-8")).hexdigest()

    @staticmethod
    def is_ignored_file(url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in IMPORTER_ASSETS_EXTENSIONS)

    @staticmethod
    def matches_ignore_patterns(url: str) -> bool:
        for pattern in IMPORTER_IGNORE_PATTERNS:
            if re.search(pattern, url):
                return True
        return False

    def crawl_page(self, url: str, main_selector: str = "main"):
        try:
            r = requests.get(url, headers=IMPORTER_HEADERS, timeout=20, allow_redirects=True)
            r.raise_for_status()
            final_url = r.url
        except Exception as e:
            self.site_map.add_error(url, e)
            return

        if final_url not in self.site_map:
            self.site_map.add_new(final_url)
        else:
            self.site_map.copy_entry(final_url, url)

        try:
            html_content = r.text
            soup = BeautifulSoup(html_content, "html.parser")

            # Add new links to state if not present
            for a in soup.find_all("a"):
                href = a.get("href")
                if not href:
                    continue
                next_url = urljoin(final_url, href)
                parsed = urlparse(next_url)
                if self.is_internal(next_url) and parsed.scheme in ("http", "https"):
                    path = urlparse(next_url).path.lower()
                    if any(path.endswith(ext) for ext in IMPORTER_ASSETS_EXTENSIONS):
                        continue
                    if self.matches_ignore_patterns(next_url):
                        if next_url not in self.site_map:
                            self.site_map.add_ignored(next_url)
                        continue
                    if next_url not in self.site_map:
                        self.site_map.add_new(next_url)

            checksum = self.get_checksum(html_content)
            file_path = f"{checksum}.html"
            with open(os.path.join(INPUT_ASSETS_PATH, f"{checksum}.html"), "w", encoding="utf-8") as f:
                f.write(html_content)

            self.site_map.add_downloaded(final_url, checksum, file_path, r.headers.get("Content-Type", ""))
        except Exception as e:
            self.site_map.add_error(url, e)
            return

    def crawl_pages(self, main_selector: str = "main"):
        print('Starting crawl...')
        print(f'Loaded {len(self.site_map)} URLs from state.')
        print('Directories ensured.')
        print('Crawling started...')
        max_workers = 8  # You can adjust this number based on your needs
        iteration = 0
        while True:
            iteration += 1
            self.site_map.load()
            to_process = self.site_map.get_new_entries()
            if not to_process:
                break
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self.crawl_page, url, main_selector): url for url in to_process}
                with tqdm(total=len(futures), unit="page", ncols=100) as pbar:
                    for future in as_completed(futures):
                        url = futures[future]
                        pbar.set_description(f"Crawling [{iteration}] {url}")
                        pbar.update(1)
        print('Crawling finished...')

    def extract_assets(self):
        for url, entry in tqdm(self.site_map.get_downloaded_entries(), desc="Extracting assets"):
            html_path = os.path.join(INPUT_ASSETS_PATH, entry.path)
            try:
                with open(html_path, "r", encoding="utf-8") as f:
                    soup = BeautifulSoup(f.read(), "html.parser")
                # Extract assets from media tags
                for tag in soup.find_all(["img", "video", "audio", "source"]):
                    src = tag.get("src")
                    if src:
                        asset_url = urljoin(url, src)
                        parsed = urlparse(asset_url)
                        ext = os.path.splitext(parsed.path)[1].lower()
                        if ext in IMPORTER_ASSETS_EXTENSIONS and asset_url not in self.assets_map:
                            self.assets_map.add_new(asset_url, False)
                # Extract directly linked assets from <a> tags
                for a in soup.find_all("a"):
                    href = a.get("href")
                    if href:
                        asset_url = urljoin(url, href)
                        parsed = urlparse(asset_url)
                        ext = os.path.splitext(parsed.path)[1].lower()
                        if ext in IMPORTER_ASSETS_EXTENSIONS and asset_url not in self.assets_map:
                            self.assets_map.add_new(asset_url, False)
            except Exception as e:
                print(f"Error parsing {html_path}: {e}")

        self.assets_map.persist()
        print('Extracting assets finished...')


    def download_assets(self):
        max_workers = 8  # You can adjust this number as needed
        asset_urls = list(self.assets_map.get_new_entries())
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.download_asset, asset_url): asset_url for asset_url in asset_urls}
            with tqdm(total=len(futures), desc="Downloading assets") as pbar:
                for future in as_completed(futures):
                    pbar.update(1)
        print('Extracting assets finished...')

    def download_asset(self, asset_url):
        try:
            r = requests.get(asset_url, headers=IMPORTER_HEADERS, timeout=20, stream=True)
            r.raise_for_status()
            content = r.content
            checksum = hashlib.sha256(content).hexdigest()
            ext = os.path.splitext(urlparse(asset_url).path)[1].lower()
            file_name = f"{checksum}{ext}"
            file_path = os.path.join(INPUT_ASSETS_PATH, file_name)
            with open(file_path, "wb") as f:
                f.write(content)
            self.assets_map.add_downloaded(asset_url, checksum, file_name, r.headers.get("Content-Type", ""))
        except Exception as e:
            self.assets_map.add_error(asset_url, e)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importer CLI")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["crawl-pages", "extract-assets", "download-assets"],
        help="Command to run"
    )
    args = parser.parse_args()

    importer = Importer()

    if args.command == "crawl-pages":
        importer.crawl_pages()
    elif args.command == "extract-assets":
        importer.extract_assets()
    elif args.command == "download-assets":
        importer.download_assets()
    else:
        importer.crawl_pages()
        importer.extract_assets()
        importer.download_assets()
