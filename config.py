import os

START_URL = "https://zspzd-technikum.pl"
OUTPUT_DIR = "zspzd-technikum.pl"

ASSETS_DIR = "assets"
ASSETS_PATH = os.path.join(OUTPUT_DIR, ASSETS_DIR)

ASSETS_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp", ".webp", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".tar", ".gz", ".ppt", ".pptx",
    ".mp4", ".mp3", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".jpe", ".odt"
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
    r"#top",  # Ignore URLs ending with #top
    # Add more patterns as needed
]

IGNORED_ELEMENT_SELECTORS = [
    ".hidden",
    ".entry-footer",
    ".post-meta-infos",
    ".comment_meta_container",
    ".comment_container",
    # Add more selectors as needed
]

MARKDONIFY_IGNORED_URLS = [
    r"\/aktualnosci\/",
    r"\/category\/",
    r"\/author\/",
    r"\/szkola\/",
    r"\/o-szkole\/$",
    r"\/dla-absolwentow\/$",
    r"\/projekty-unijne\/$",
    r"\/zgloszenie-na-konkurs-z-pokroju-bydla\/$",
    r"\/\d{4}\/\d{2}\/$",
    r"\/\d{4}\/\d{2}\/\d{2}\/$",
    r"\/\d{4}\/\d{2}\/page/\d*\/$",
]

MARKDONIFY_REMAP_URLS = {
    r"(\d{4})\/(\d{2})\/(\d{2})\/(.*)":r"aktualnosci/\1-\2-\3-\4",
}

BROKEN_LINKS_MAP = {
    '../wp-content/': 'https://zspzd-technikum.pl/wp-content/'
}