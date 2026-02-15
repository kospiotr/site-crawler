import copy
import os
import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import config
from config import *
from sitemap import Sitemap, SitemapStatus, SitemapEntry

for d in [ASSETS_PATH]:
    os.makedirs(d, exist_ok=True)

sitemap = Sitemap(SITEMAP_CSV, START_URL)
sitemap_lock = threading.Lock()

def is_internal(url: str) -> bool:
    return urlparse(url).netloc in ("", domain)

def get_checksum(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()

visited = set()
domain = urlparse(START_URL).netloc


def is_ignored_file(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in IGNORED_CRAWLING_EXTENSIONS)


def matches_ignore_patterns(url: str) -> bool:
    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, url):
            return True
    return False


def crawl(url: str, main_selector: str = "main"):
    with sitemap_lock:
        sitemap.print_summary()
        if url in sitemap and sitemap[url] in ("completed", "ignored", "error"):
            return

    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        r.raise_for_status()
        final_url = r.url
    except Exception as e:
        with sitemap_lock:
            sitemap[url] = SitemapEntry(SitemapStatus.ERROR, error=str(e))
            sitemap.persist()
        return

    with sitemap_lock:
        # Register in state if not present
        if final_url not in sitemap:
            sitemap[final_url] = SitemapEntry(SitemapStatus.REGISTERED)
            sitemap.persist()
        else:
            existing_entry: SitemapEntry = copy.copy(sitemap[final_url])
            sitemap[url] = existing_entry
            sitemap.persist()

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
            if is_internal(next_url) and parsed.scheme in ("http", "https"):
                if is_ignored_file(next_url):
                    continue
                if matches_ignore_patterns(next_url):
                    with sitemap_lock:
                        if next_url not in sitemap:
                            sitemap[next_url] = SitemapEntry(SitemapStatus.IGNORED)
                            sitemap.persist()
                    continue
                with sitemap_lock:
                    if next_url not in sitemap:
                        sitemap[next_url] = SitemapEntry(SitemapStatus.REGISTERED)
                        sitemap.persist()

        checksum = get_checksum(html_content)
        file_path = f"{checksum}.html"
        with open(os.path.join(ASSETS_PATH, f"{checksum}.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

        with sitemap_lock:
            sitemap[url] = sitemap[final_url] = SitemapEntry(SitemapStatus.DOWNLOADED, hash=checksum, path=file_path, mimetype=r.headers.get("Content-Type", ""))
            sitemap.persist()
    except Exception as e:
        with sitemap_lock:
            sitemap[url] = sitemap[final_url] = SitemapEntry(SitemapStatus.ERROR, error=str(e))
            sitemap.persist()
        return

def crawl_pages(main_selector: str = "main"):
    print('Starting crawl...')
    print(f'Loaded {len(sitemap)} URLs from state.')
    print('Directories ensured.')
    print('Crawling started...')
    max_workers = 8  # You can adjust this number based on your needs

    while True:
        sitemap.load()
        with sitemap_lock:
            to_process = [url for url, data in sitemap.items() if data.status == SitemapStatus.REGISTERED]
        if not to_process:
            break

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(crawl, url, main_selector) for url in to_process]
            for future in as_completed(futures):
                pass  # Results are handled inside crawl

    print('Crawling finished...')

def collect_and_download_assets():
    print("Collecting and downloading assets...")
    asset_urls = set()
    for url, entry in sitemap.items():
        if entry.status == SitemapStatus.DOWNLOADED and entry.path:
            html_path = os.path.join(ASSETS_PATH, entry.path)
            try:
                with open(html_path, "r", encoding="utf-8") as f:
                    soup = BeautifulSoup(f.read(), "html.parser")
                for tag in soup.find_all(["img", "video", "audio", "source"]):
                    src = tag.get("src")
                    if src:
                        asset_url = urljoin(url, src)
                        parsed = urlparse(asset_url)
                        ext = os.path.splitext(parsed.path)[1].lower()
                        if ext in ALLOWED_ASSETS_FILE_EXTENSIONS:
                            asset_urls.add(asset_url)
            except Exception as e:
                print(f"Error parsing {html_path}: {e}")

    for asset_url in tqdm(asset_urls, desc="Downloading assets"):
        if asset_url in sitemap and sitemap[asset_url].status == SitemapStatus.DOWNLOADED:
            continue
        try:
            r = requests.get(asset_url, headers=HEADERS, timeout=20, stream=True)
            r.raise_for_status()
            content = r.content
            checksum = hashlib.sha256(content).hexdigest()
            ext = os.path.splitext(urlparse(asset_url).path)[1].lower()
            file_name = f"{checksum}{ext}"
            file_path = os.path.join(ASSETS_PATH, file_name)
            with open(file_path, "wb") as f:
                f.write(content)
            sitemap[asset_url] = SitemapEntry(
                status=SitemapStatus.DOWNLOADED,
                hash=checksum,
                path=file_name,
                mimetype=r.headers.get("Content-Type", "")
            )
            sitemap.persist()
        except Exception as e:
            sitemap[asset_url] = SitemapEntry(
                status=SitemapStatus.ERROR,
                error=str(e)
            )
            sitemap.persist()

if __name__ == "__main__":
    crawl_pages()
    collect_and_download_assets()
