import os

BUILD_DIR = "build"
IMPORTER_DOMAIN = "zspzd-technikum.pl"
IMPORTER_START_URL = f"https://{IMPORTER_DOMAIN}"
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
TRANSFORMED_BROKEN_LINKS_CSV = os.path.join(TRANSFORMED_DIR, 'report_broken_links.csv')
TRANSFORMED_IGNORED_ELEMENT_SELECTORS = [
    ".hidden",
    ".entry-footer",
    ".post-meta-infos",
    ".comment_meta_container",
    ".comment_container",
    # Add more selectors as needed
]

TRANSFORMED_REMAP_URLS = {
    # wp-specific
    r"\?p\=(.*)":r"page_\1",
    r"\?attachment_id\=(.*)":r"attachment_\1",
    f'{IMPORTER_START_URL}$':f'{IMPORTER_START_URL}/_index_1',
    f'{IMPORTER_START_URL}/$':f'{IMPORTER_START_URL}/_index_2',

    # site-specific
    r"(\d{4})\/(\d{2})\/(\d{2})\/(.*)":r"aktualnosci/\1/\2/\3-\4",
    r"\/o-szkole\/baza-szkoly\/":r"/o-szkole/baza-szkoly/",
    r"\/o-szkole\/galeria\/":r"/o-szkole/baza-szkoly/galeria/",
    r"\/o-szkole\/samorzad-uczniowski\/":r"/dla-ucznia-i-opiekuna/samorzad-uczniowski",
    r"\/o-szkole\/kontakt\/":r"/kontakt/dane-kontaktowe",
    r"\/o-szkole\/kola-zainteresowan\/":r"/co-robimy/kola-zainteresowan",
    r"\/o-szkole\/patronka\/":r"/o-szkole/patronka",
    r"\/o-szkole\/kadra\/":r"/o-szkole/pracownicy-szkoly/kierownictwo",
    r"\/o-szkole\/kalendarium\/":r"/o-szkole/kalendarium",
    r"\/o-szkole\/osiagniecia\/rok-szkolny-20142015":r"/o-szkole/sukcesy/sukcesy-2014-2015",
    r"\/o-szkole\/osiagniecia\/sukcesy-20152016":r"/o-szkole/sukcesy/sukcesy-2015-2016",
    r"\/o-szkole\/osiagniecia\/sukcesy-20162017":r"/o-szkole/sukcesy/sukcesy-2016-2017",
    r"\/o-szkole\/osiagniecia\/sukcesy-20172018":r"/o-szkole/sukcesy/sukcesy-2017-2018",
    r"\/o-szkole\/osiagniecia\/":r"/o-szkole/sukcesy/",
    r"\/o-szkole\/sukcesy\/sukcesy-(.*)\/":r"/o-szkole/sukcesy/\1",

    r"\/dla-absolwentow\/":r"/co-robimy/dla-absolwentow/",

    r"\/oferta-edukacyjna\/kierunki-ksztalcenia\/":r"/co-robimy/kierunki-ksztalcenia/",
    r"\/oferta-edukacyjna\/$":r"/co-robimy/oferta-edukacyjna/",
    r"\/oferta-edukacyjna\/dni-otwarte-szkoly\/":r"/co-robimy/dni-otwarte-szkoly",
    r"\/oferta-edukacyjna\/rekrutacja\/":r"/co-robimy/rekrutacja",
    r"\/oferta-edukacyjna\/dokumenty-do-pobrania\/":r"/o-szkole/dokumenty-do-pobrania",

    r"\/projekty-unijne\/era[sz]mus-*(.*)":r"/co-robimy/projekty-erasmus-plus/erasmus-\1",
    r"\/projekty-unijne\/fers-2025":r"/co-robimy/projekty-erasmus-plus/fers-2025",
    r"\/projekty-unijne\/ldv":r"/co-robimy/projekty-erasmus-plus/ldv-2013",
    r"\/projekty-unijne\/power-2017-2019":r"/co-robimy/projekty-erasmus-plus/power-2017-2019",
    r"\/projekty-unijne\/fedl-fundusze-europejskie-dla-lodzkiego-2024-2026\/":r"/co-robimy/projekty-funduszy-regionalnych/fedl-fundusze-europejskie-dla-lodzkiego-2024-2026/",
    r"\/projekty-unijne\/nauczanie-rolnicze-xxi-wieku-modernizacja-i-rozbudowa-bazy-ksztalcenia-zawodowego-w-zespole-szkol-centrum-ksztalcenia-rolniczego-im-jadwigi-dziubinskiej-w-zdunskiej-dabrowie\/":r"/co-robimy/projekty-funduszy-regionalnych/nauczanie-rolnicze-xxi-wieku-modernizacja-i-rozbudowa-bazy-ksztalcenia-zawodowego-w-zespole-szkol-centrum-ksztalcenia-rolniczego-im-jadwigi-dziubinskiej-w-zdunskiej-dabrowie/",
    r"\/projekty-unijne\/projekt-nr-rpld-11-03-01\/":r"/co-robimy/projekty-funduszy-regionalnych/projekt-nr-rpld-11-03-01/",
    r"\/projekty-unijne\/nfosigw-1-3-1\/":r"/co-robimy/projekty-nfosigw/nfosigw-1-3-1/",
    r"\/projekty-unijne\/rpo-absolwent-na-rynku-pracy\/":r"/co-robimy/projekty-funduszy-regionalnych/rpo-absolwent-na-rynku-pracy/",
    r"\/projekty-unijne\/efrrow\/":r"/co-robimy/projekty-funduszy-regionalnych/efrrow/",
    r"\/projekty-unijne\/kuznia-mlodego-przedsiebircy\/":r"/co-robimy/projekty-funduszy-regionalnych/kuznia-mlodego-przedsiebircy/",
    r"\/projekty-unijne\/rpo-nauczanie-rolnicze-xxi-wieku-mlodzi-na-start\/":r"/co-robimy/projekty-funduszy-regionalnych/rpo-nauczanie-rolnicze-xxi-wieku-mlodzi-na-start/",
    r"\/fundusze-europejskie-dla-lodzkiego\/":r"/co-robimy/projekty-funduszy-regionalnych/rpo-nauczafundusze-europejskie-dla-lodzkiego/",
    r"\/wfosigw\/":r"/co-robimy/projekty-wfosigw/",

    r"\/oferty-pracy\/":r"/co-robimy/oferty-pracy/",
    r"\/zjazd-w-szkolach-dla-doroslych\/":r"/co-robimy/szkoly-dla-doroslych/",
    r"\/dla-rodzicow/kursy-kwalifikacyjne/terminy-zjazdow\/":r"/co-robimy/szkoly-dla-doroslych/terminy-zjazdow/",

    r"\/dla-rodzicow\/kursy-kwalifikacyjne\/":r"/co-robimy/szkoly-dla-doroslych/kursy-kwalifikacyjne/",
    r"\/dla-rodzicow\/egzamin-maturalny\/":r"/dla-ucznia-i-opiekuna/egzaminy-zawodowe/",
    r"\/dla-rodzicow\/$":r"/dla-ucznia-i-opiekuna/dla-opiekunow/",
    r"\/dla-rodzicow\/":r"/dla-ucznia-i-opiekuna/",

    r"\/rodo\/":r"/o-szkole/ochrona-danych-osobowych/rodo",
}

TRANSFORMED_IGNORED_URLS = [
    # wp-specific
    f'{IMPORTER_START_URL}$',
    f'{IMPORTER_START_URL}/$',
    r"\/wp\-login\.php",
    r"\/feed\/",
    r"\?attachment_id\=(.*)",
    r"\?p\=(.*)",
    r"\/wp-admin",
    r"\/wp-content",
    r"\/comments",
    r"\/aktualnosci\/",
    r"\/\d{4}\/\d{2}\/$",
    r"\/\d{4}\/\d{2}\/\d{2}\/$",
    r"\/\d{4}\/\d{2}\/page/\d*\/$",
    r"\/\d{4}\/\d{2}\/\d{2}\/page/\d*\/$",
    r"\/\d{4}\/\d{2}\/\d{2}\/.+\/.+",
    r"\/category\/",
    r"\/author\/",

    # site-specific
    r"\/szkola\/",
    r"\/o-szkole\/$",
    r"\/o-szkole\/wolontariat\/$",
    r"\/dla-absolwentow\/$",
    r"\/projekty-unijne\/$",
    r"\/o-szkole\/osiagniecia\/$",
    r"\/oferta-edukacyjna\/kierunki-ksztalcenia\/$",
    r"\/wfosigw\/$",
    r"\/filmy",
    r"\/oferty-pracy/$",

    r"\/oferta-pracy-nr-3-na-stanowisko-specjalista-ds-szkolen-w-bcu-w-zdunskiej-dabrowie",
    r"\/zgloszenie-na-konkurs-z-pokroju-bydla\/$",
    r"\/przebudowa-poligonu-nauki-jazdy-na-plac-manewrowy\/$",
    r"\/podanie-do-sp\/$",
    r"\/mlodziez-ze-zdunskiej-dabrowy-uczestniczy-w-projekcie-lokalna-wies-miejscem-do-zycia-i-rozwoju\/$",
    r"\/turnieju-dla-uczniow-szkol-srednich-o-puchar-komendanta-wojewodzkiego-policji-w-lodzi\/$",
    r"\/dla-rodzicow/plan-lekcji\/$",
    r"\/dla-absolwentow\/formularz-zgloszeniowy-na-zjazd-absolwentow\/$",
    r"\/oferta-edukacyjna\/kierunki-ksztalcenia\/szczegolowa-oferta-edukacyjna\/$",
]


TRANSFORMER_TITLE_ADJUSTER = lambda title: title.replace(' – Zespół Szkół Centrum Kształcenia Rolniczego  im. Jadwigi Dziubińskiej w Zduńskiej Dąbrowie','').strip()

BROKEN_LINKS_MAP = {
    '../wp-content/': 'https://zspzd-technikum.pl/wp-content/'
}

PUBLISHER_IMAGES_EXT = ['.jpg', '.jpe', '.jpeg', '.png', '.gif', '.svg', '.bmp', '.webp', '.ico']

FIXED_DIR = os.path.join(BUILD_DIR, "transformed-fixed")
OUTPUT_DIR = os.path.join(BUILD_DIR, "output")