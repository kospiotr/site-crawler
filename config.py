import os

BUILD_DIR = "build"
IMPORTER_START_URL = "https://zspzd-technikum.pl"
INPUT_DIR = "input"
INPUT_ASSETS_DIR = "assets"
INPUT_ASSETS_PATH = os.path.join(BUILD_DIR, INPUT_DIR, INPUT_ASSETS_DIR)
INPUT_SITE_MAP_CSV = os.path.join(BUILD_DIR, INPUT_DIR, "map.site.csv")
INPUT_ASSETS_MAP_CSV = os.path.join(BUILD_DIR, INPUT_DIR, "map.assets.csv")

IMPORTER_ASSETS_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp", ".webp", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".tar", ".gz", ".ppt", ".pptx",
    ".mp4", ".mp3", ".avi", ".mov", ".wmv", ".flv", ".mkv", ".jpe", ".odt"
)
IMPORTER_HEADERS = {
    "User-Agent": "Crawler/1.0"
}
IMPORTER_IGNORE_PATTERNS = [
    r"logout",
    r"/private/",
    r"\?s=$",  # Ignore URLs ending with ?s=
    r"#top",  # Ignore URLs ending with #top
    # Add more patterns as needed
]

TRANSFORMED_DIR = os.path.join(BUILD_DIR, "transformed")
TRANSFORMED_ASSETS_DIR = os.path.join(TRANSFORMED_DIR, "assets")
TRANSFORMED_IGNORED_ELEMENT_SELECTORS = [
    ".hidden",
    ".entry-footer",
    ".post-meta-infos",
    ".comment_meta_container",
    ".comment_container",
    # Add more selectors as needed
]
TRANSFORMED_IGNORED_URLS = [
    r"\/aktualnosci\/",
    r"\/category\/",
    r"\/author\/",
    r"\/szkola\/",
    r"\/o-szkole\/$",
    r"\/o-szkole\/wolontariat\/$",
    r"\/dla-absolwentow\/$",
    r"\/projekty-unijne\/$",
    r"\/zgloszenie-na-konkurs-z-pokroju-bydla\/$",
    r"\/\d{4}\/\d{2}\/$",
    r"\/\d{4}\/\d{2}\/\d{2}\/$",
    r"\/\d{4}\/\d{2}\/page/\d*\/$",
    r"\/\d{4}\/\d{2}\/\d{2}\/page/\d*\/$",
]

TRANSFORMED_REMAP_URLS = {
    r"(\d{4})\/(\d{2})\/(\d{2})\/(.*)":r"aktualnosci/\1/\2/\1-\2-\3-\4",
}

BROKEN_LINKS_MAP = {
    '../wp-content/': 'https://zspzd-technikum.pl/wp-content/'
}