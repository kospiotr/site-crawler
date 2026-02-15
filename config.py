import os

START_URL = "https://zspzd-technikum.pl"
OUTPUT_DIR = "zspzd-technikum.pl"

ASSETS_DIR = "assets"
ASSETS_PATH = os.path.join(OUTPUT_DIR, ASSETS_DIR)

ALLOWED_ASSETS_FILE_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp", ".webp", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".tar", ".gz", ".ppt", ".pptx",
    ".mp4", ".mp3", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".jpe"
)

IGNORED_CRAWLING_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp", ".webp", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".tar", ".gz", ".ppt", ".pptx",
    ".mp4", ".mp3", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".jpe"
)

HEADERS = {
    "User-Agent": "Crawler/1.0"
}

SITEMAP_CSV = os.path.join(OUTPUT_DIR, "map.site.csv")
ASSETSMAP_CSV = os.path.join(OUTPUT_DIR, "map.assets.csv")

IGNORE_PATTERNS = [
    r"logout",
    r"/private/",
    r"\?s=$",  # Ignore URLs ending with ?s=
    # Add more patterns as needed
]

IGNORED_ELEMENT_SELECTORS = [
    ".hidden",
    ".entry-footer",
    # Add more selectors as needed
]