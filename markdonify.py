import os
import re
import shutil
import urllib.parse
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from tqdm import tqdm

from config import OUTPUT_DIR, ASSETS_PATH, SITEMAP_CSV, ASSETSMAP_CSV, IGNORED_ELEMENT_SELECTORS, BROKEN_LINKS_MAP, MARKDONIFY_IGNORED_URLS, MARKDONIFY_REMAP_URLS
from sitemap import Sitemap

MARKDOWN_DIR = os.path.join(OUTPUT_DIR, "markdown")
MARKDOWN_ASSETS_DIR = os.path.join(MARKDOWN_DIR, "assets")
shutil.rmtree(MARKDOWN_DIR, ignore_errors=True)
os.makedirs(MARKDOWN_DIR, exist_ok=True)
os.makedirs(MARKDOWN_ASSETS_DIR, exist_ok=True)

site_map = Sitemap(SITEMAP_CSV, None)
assets_map = Sitemap(ASSETSMAP_CSV, None)

# # Copy assets to markdown/assets
# for url, entry in tqdm(assets_map.items(), desc="Copying assets"):
#     if entry.status.name == "DOWNLOADED" and entry.path:
#         src = os.path.join(ASSETS_PATH, entry.path)
#         dst = os.path.join(MARKDOWN_ASSETS_DIR, entry.path)
#         if os.path.exists(src):
#             shutil.copy2(src, dst)

def remap_url(url):
    for pattern, repl in MARKDONIFY_REMAP_URLS.items():
        if re.search(pattern, url):
            return re.sub(pattern, repl, url)
    return url

def url_to_md_path(url, base_dir=MARKDOWN_DIR):
    url = remap_url(url)
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip('/')
    if path.startswith('/'):
        path = path[1:]
    path = os.path.splitext(path)[0] + '.md'
    safe_path = os.path.normpath(path)
    return os.path.join(base_dir, safe_path)

def get_relative_path(from_path, to_path):
    return os.path.relpath(to_path, os.path.dirname(from_path))

def fix_broken_link(link):
    for broken, fixed in BROKEN_LINKS_MAP.items():
        if broken in link:
            link = link.replace(broken, fixed)
    return link

def convert_links_and_assets(soup, current_md_path):
    # Convert <a> and <img> and other asset links to local
    for tag in soup.find_all(["a", "img", "audio", "video", "source"]):
        attr = "href" if tag.name == "a" else "src"
        link = tag.get(attr)
        if not link:
            continue
        # Fix broken links using BROKEN_LINKS_MAP
        link = fix_broken_link(link)
        # Convert page links
        if link in url_to_md:
            rel_path = get_relative_path(current_md_path, url_to_md[link])
            tag[attr] = rel_path
        # Convert asset links
        elif link in asset_to_local:

            asset_name = asset_to_local[link]
            asset_abs_path = os.path.join(MARKDOWN_DIR, asset_name)
            rel_path = get_relative_path(current_md_path, asset_abs_path)
            tag[attr] = rel_path
            src = os.path.join(OUTPUT_DIR, asset_name)
            dst = os.path.join(MARKDOWN_DIR, asset_name)
            if os.path.exists(src):
                shutil.copy2(src, dst)
    return soup

# # Build url to md and asset to local maps
url_to_md = {}
for url, entry in tqdm(site_map.items(), desc="Building url to md map"):
    if entry.status.name == "DOWNLOADED" and entry.path:
        url_to_md[url] = url_to_md_path(url, base_dir=MARKDOWN_DIR)
asset_to_local = {}
for url, entry in tqdm(assets_map.items(), desc="Building asset to local map"):
    if entry.status.name == "DOWNLOADED" and entry.path:
        asset_to_local[url] = os.path.join("assets", entry.path)

def remove_ignored_elements(soup: BeautifulSoup):
    for selector in IGNORED_ELEMENT_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

def should_ignore_page(url):
    for pattern in MARKDONIFY_IGNORED_URLS:
        if re.search(pattern, url):
            return True
    return False

# Process each downloaded page
for url, entry in tqdm(site_map.items(), desc="Processing pages"):
    if entry.status.name != "DOWNLOADED" or not entry.path:
        continue
    if should_ignore_page(url):
        continue
    html_path = os.path.join(ASSETS_PATH, entry.path)
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    # Extract <main>
    remove_ignored_elements(soup)
    main_elem = soup.find("main")
    if not main_elem:
        continue
    # Convert links and assets
    md_path = url_to_md[url]
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    main_elem = convert_links_and_assets(main_elem, md_path)
    # Markdownify
    markdown_content = md(str(main_elem), heading_style="ATX")
    # Extract title
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    # Header
    header = f"---\ntitle: {title}\noriginal_url: {url}\nchecksum: {entry.hash}\n---\n\n"
    # Write markdown file
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(markdown_content)
