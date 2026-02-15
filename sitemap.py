import csv
import os
from dataclasses import dataclass
from enum import Enum
from rich.live import Live
from rich.table import Table

class SitemapStatus(Enum):
    REGISTERED = "registered"
    DOWNLOADED = "downloaded"
    IGNORED = "ignored"
    ERROR = "error"

@dataclass
class SitemapEntry:
    status: SitemapStatus = None
    hash: str = None
    path: str = None
    mimetype: str = None
    error: str = None

class Sitemap(dict[str, SitemapEntry]):

    file_path: str = None
    start_url: str = None

    def __init__(self, file_path: str, start_url: str):
        super().__init__()
        self.file_path = file_path
        self.start_url = start_url

        self.load()
        if not self:
            self.init()
            self.load()

    def init(self):
        self[self.start_url] = SitemapEntry(SitemapStatus.REGISTERED)
        self.persist()

    def load(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row["url"]
                    status = SitemapStatus(row.get("status"))
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


if __name__ == "__main__":
    sitemap = Sitemap("sitemap.csv", "https://zspzd-technikum.pl")
    print(sitemap)