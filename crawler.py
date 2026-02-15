import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from tqdm import tqdm
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from config import *
from sitemap import Sitemap

for d in [ASSETS_PATH]:
    os.makedirs(d, exist_ok=True)

site_map = Sitemap(SITEMAP_CSV, START_URL)
assets_map = Sitemap(ASSETSMAP_CSV, START_URL)

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
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        r.raise_for_status()
        final_url = r.url
    except Exception as e:
        site_map.add_error(url, e)
        return

    if final_url not in site_map:
        site_map.add_new(final_url)
    else:
        site_map.copy_entry(final_url, url)

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
                    if next_url not in site_map:
                        site_map.add_ignored(next_url)
                    continue
                if next_url not in site_map:
                    site_map.add_new(next_url)

        checksum = get_checksum(html_content)
        file_path = f"{checksum}.html"
        with open(os.path.join(ASSETS_PATH, f"{checksum}.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

        site_map.add_downloaded(final_url, checksum, file_path, r.headers.get("Content-Type", ""))
    except Exception as e:
        site_map.add_error(url, e)
        return

def crawl_pages(main_selector: str = "main"):
    print('Starting crawl...')
    print(f'Loaded {len(site_map)} URLs from state.')
    print('Directories ensured.')
    print('Crawling started...')
    max_workers = 8  # You can adjust this number based on your needs
    iteration = 0
    while True:
        iteration += 1
        site_map.load()
        to_process = site_map.get_new_entries()
        if not to_process:
            break
        with tqdm(to_process, unit="page", ncols=100) as pbar:
            for url in pbar:
                pbar.set_description(f"Crawling [{iteration}]")
                crawl(url, main_selector)
    print('Crawling finished...')

def collect_assets():
    for url, entry in tqdm(site_map.get_downloaded_entries(), desc="Extracting assets"):
        html_path = os.path.join(ASSETS_PATH, entry.path)
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
                    if ext in ALLOWED_ASSETS_FILE_EXTENSIONS and asset_url not in site_map:
                        assets_map.add_new(asset_url)
            # Extract directly linked assets from <a> tags
            for a in soup.find_all("a"):
                href = a.get("href")
                if href:
                    asset_url = urljoin(url, href)
                    parsed = urlparse(asset_url)
                    ext = os.path.splitext(parsed.path)[1].lower()
                    if ext in ALLOWED_ASSETS_FILE_EXTENSIONS and asset_url not in site_map:
                        assets_map.add_new(asset_url)
        except Exception as e:
            print(f"Error parsing {html_path}: {e}")

def download_assets():
    for asset_url in tqdm(assets_map.get_new_entries(), desc="Downloading assets"):
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
            assets_map.add_downloaded(asset_url, checksum, file_name, r.headers.get("Content-Type", ""))
        except Exception as e:
            assets_map.add_error(asset_url, e)

if __name__ == "__main__":
    crawl_pages()
    collect_assets()
    download_assets()
