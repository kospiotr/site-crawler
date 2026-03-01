import argparse
import re
import shutil
import time
import uuid
import yaml

import markdown
import requests
import requests
import base64
import mimetypes
import json
import os

from tqdm import tqdm

from config import OUTPUT_DIR
from config import TRANSFORMED_DIR

config = {
    'url': 'https://www.gov.pl/web/zsckr-zdunska-dabrowa',
    'site_id': '20003421',
    'repository': {
        'images_root_id': '2c907143-e3cf-451b-ab0e-aa915030c43b',
        'attachments_root_id': 'a7b3e0cf-d9d7-4182-8898-beb7807528a5',
    },
    'cookies': {
        'JSESSIONID': '49DD317766015E7E4B7A71681B89A775',
        'XSRF-TOKEN': '01d64644-c951-4ff0-aee5-3b3cb920b8cc',
    }
}

class MarkdownParser:

    def __init__(self, file_path):
        with open(file_path, encoding="utf-8") as f:
            self.raw_content = f.read()
        self.frontmatter = {}
        self.main_content = self.raw_content
        if self.raw_content.startswith("---"):
            parts = self.raw_content.split("---", 2)
            if len(parts) > 2:
                fm_text = parts[1]
                self.main_content = parts[2].lstrip("\n")
                try:
                    self.frontmatter = yaml.safe_load(fm_text)
                except Exception as e:
                    print(f"YAML frontmatter parse error: {e}")

    def get_title(self):
        return self.frontmatter.get("title")

    def get_date(self):
        return self.frontmatter.get("date")

    def get_html(self):
        return markdown.markdown(self.main_content)


class RedakcjaGovPlClient:
    base_url: str = 'https://redakcja.www.gov.pl'
    site_id: str = None
    session = requests.Session()
    cookies: dict[str, str] = []

    def __init__(self, site_id: str, cookies: dict[str, str]):
        self.site_id = site_id
        self.cookies = cookies

    def get_pages(self):
        return requests.get(
            f'{self.base_url}/api/v2/sites/{self.site_id}/pages?',
            headers={
                'accept': 'application/json, text/plain, */*',
            },
            cookies=self.cookies
        ).json()

    def post_page(self, parent_page_id: str, type: str, name: str, displayed_path: str):
        displayed_path = displayed_path.removeprefix('/')
        return requests.post(
            f'{self.base_url}/api/v2/sites/{self.site_id}/pages?parentPageId={parent_page_id}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies,
            json={"pages": [], "registers": [], "renderChildrenComponents": False, "isAccessPermited": False,
                  "type": type, "showInSiteMenu": True, "name": name,
                  "displayedPath": displayed_path}
        ).json()

    def post_page_move(self, page_id: str, order_number: int, parent_page_id):
        return requests.post(
            f'{self.base_url}/api/v2/pages/{page_id}/translations/pl_PL/move/{parent_page_id}/{order_number}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies
        ).json()

    def get_repo_folders(self, parent_folder_id: str):
        return requests.get(
            f'{self.base_url}/api/v2/repo/folders/{parent_folder_id}/content',
            headers={
                'accept': 'application/json, text/plain, */*',
            },
            cookies=self.cookies
        ).json()

    def create_repo_folder(self, parent_folder_id: str, name: str):
        return requests.post(
            f'{self.base_url}/api/v2/repo/folders/{parent_folder_id}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'content-type': 'application/json',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies,
            json={
                "name": name,
                "hidden": False
            }
        ).json()

    def delete_repo_folder(self, folder_id: str):
        return requests.delete(
            f'{self.base_url}/api/v2/repo/folders/{folder_id}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'content-type': 'application/json',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies
        )

    def upload_image(self, folder_id, file_path, description):
        # Guess the mime type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        # Read and encode file
        with open(file_path, 'rb') as f:
            file_bytes = f.read()
            encoded = base64.b64encode(file_bytes).decode('utf-8')

        # Prepare metadata
        metadata = {
            "folderId": folder_id,
            "hidden": False,
            "width": 64,  # Set actual width if needed
            "height": 64,  # Set actual height if needed
            "activeFormat": None,
            "fileContent": {
                "lastModified": 1771624425167,
                "lastModifiedDate": "Fri Feb 20 2026 22:53: 45 GMT+0100 (Central European Standard Time)",
                "name": os.path.basename(file_path),
                "size": 780,
                "type": mime_type
            },
            "name": os.path.basename(file_path),
            "encodedFileContent": f"data:{mime_type};base64,{encoded}",
            "trustedStyleUrl": {
                "changingThisBreaksApplicationSecurity": f"url(data:{mime_type};base64,{encoded})"
            },
            "description": description,
            "alternativeDescription": description,
            "tags": None,
            "source": None
        }

        # Prepare multipart form data
        files = {
            "file": (os.path.basename(file_path), file_bytes, mime_type),
            "metadata": ("metadata.json", json.dumps(metadata), "application/json")
        }

        response = requests.post(
            f"{self.base_url}/api/v2/repo/photos/",
            files=files,
            cookies=self.cookies,
            headers={
                'accept': 'application/json, text/plain, */*',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            }
        )
        return response.json()

    def put_page_sketch(self, page_id: str, from_version: str):
        return requests.put(
            f'{self.base_url}/api/v2/page/{page_id}/from/version/{from_version}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies
        ).json()

    def put_page_version(self, page_id: str, from_version: str, content: str, name: str, displayedPath: str):
        request_body = {
                "content": {
                    "article": {
                        "logos": [],
                        "euBeneficiariesLogos": {
                            "euFundsLogo": {
                                "id": None,
                                "alt": None
                            },
                            "euLogo": {
                                "id": None,
                                "alt": None
                            },
                            "customLogos": [],
                            "logosUnderTitle": False
                        },
                        "photo": None,
                        "position": None,
                        "intro": None,
                        "sections": [
                            {
                                "textSections": [
                                    {
                                        "title": "",
                                        "textHtml": content,
                                        "headerStyle": "DEFAULT",
                                        "id": "0"
                                    }
                                ],
                                "links": [],
                                "youTubeLinkSections": []
                            }
                        ],
                        "questionnaire": {
                            "url": None
                        },
                        "event": {
                            "location": None,
                            "date": "2003-02-01T00:00:00",
                            "expireDate": None,
                            "eventDateStart": None,
                            "eventDateEnd": None,
                            "eventTimeStart": None,
                            "eventTimeEnd": None,
                            "addressFromFooter": False,
                            "voivodeship": None,
                            "city": None,
                            "street": None,
                            "description": None,
                            "dateDescription": None,
                            "locationDescription": None,
                            "accreditation": False,
                            "sendMessage": False,
                            "journalistDescription": None,
                            "transmissionCarsDescription": None,
                            "accreditationData": None
                        },
                        "legalBasis": [],
                        "gallery": [
                        ],
                        "status": {
                            "name": None,
                            "startDate": None,
                            "endDate": None
                        },
                        "metrics": {
                            "validUntilDate": None,
                            "changesDone": None
                        },
                        "accordionAttribute": None,
                        "showMetrics": False
                    },
                    "publicProcurement": None,
                    "jobOffer": None,
                    "document": None,
                    "disclaimerEnabled": None,
                    "serviceCard": None,
                    "serviceCardCUS": None,
                    "register": None,
                    "card": None,
                    "contactCard": None,
                    "govCard": None,
                    "competition": None,
                    "globalSearch": False,
                    "informationCard": None,
                    "graphicGallery": None
                },
                "config": {
                    "htmlHeadTitle": None,
                    "headerTitle": None,
                    "socialShareImage": None,
                    "socialShareIntro": None,
                    "showBreadcrumbs": True,
                    "showMetrics": False,
                    "showArticleChildrenLinks": True,
                    "backgroundPhoto": None,
                    "showNavigationMenu": None,
                    "showReturnButton": True,
                    "pageRedirectUrl": {
                        "redirectUrl": None,
                        "redirectUrlPageId": None
                    },
                    "menu": {
                        "showChildrenPages": None,
                        "showSiblingsPages": None
                    },
                    "sideMenuLinkId": None,
                    "tags": None,
                    "doNotShowLogos": False,
                    "sections": [
                        {
                            "type": "PAGE_CONTENT",
                            "sectionId": "aGJeSsaf6y",
                            "title": None,
                            "description": None,
                            "content": None,
                            "hideHeader": None,
                            "hideSkipLink": None,
                            "registerType": None
                        }
                    ],
                    "delayedPublishDate": None,
                    "delayedUnpublishDate": None,
                    "sdgTag": False,
                    "sdgContent": {
                        "sdgLables": None,
                        "sdgPolicyCodes": None
                    },
                    "govCard": {
                        "group": None,
                        "category": None,
                        "siteIds": None,
                        "electronicService": None
                    },
                    "pageRateSurvey": {
                        "showSurvey": False,
                        "hashedSurveyId": None
                    },
                    "metadata": {
                        "register": {
                            "columns": []
                        }
                    }
                },
                "type": "ARTICLE",
                "displayedPath": displayedPath,
                "bip": False,
                "recommendedForMainSite": False,
                "promotedOnRootPage": False,
                "promotedOnRootPageG2": False,
                "name": name,
                "originator": None
            }
        return requests.put(
            f'{self.base_url}/api/v2/page/{page_id}/version/{from_version}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies,
            json=request_body
        ).json()

    def get_page_version_history(self, page_id: str):
        return requests.get(
            f'{self.base_url}/api/v2/page/{page_id}/version-history',
            headers={
                'accept': 'application/json, text/plain, */*',
                'content-type': 'application/json',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies
        ).json()


class PagesRepository:
    dry_run = True

    def __init__(self):
        self.client = RedakcjaGovPlClient(config['site_id'], config['cookies'])
        self.load_from_file()

    def load_from_file(self):
        with open(os.path.join(OUTPUT_DIR, "pages.json"), "r", encoding="utf-8") as f:
            self.pages = json.load(f)

    def dump(self):
        timestamp = int(time.time())
        with open(os.path.join(OUTPUT_DIR, f"pages.json"), "w", encoding="utf-8") as f:
            json.dump(self.pages, f, indent=2)

    def get_page_by_path(self, relative_path):
        pass

    @staticmethod
    def nested_url_from_path(rel_path):
        return os.path.splitext(rel_path)[0]

    @staticmethod
    def absolute_url_from_path(rel_path):
        path_no_ext = os.path.splitext(rel_path)[0]
        url = re.sub(r'[^a-zA-Z0-9_-]', '-', path_no_ext)
        return url

    def find_page(self, path, pages=None):
        if not path:
            return None
        if not pages:
            pages = self.pages

        for page in pages:
            if page.get("displayedPath") == '/' + path:
                return page
            if "pages" in page and page["pages"]:
                found = self.find_page(path, page["pages"])
                if found:
                    return found
        return None

    def find_page_for_path(self, path):
        out = self.find_page(self.absolute_url_from_path(path))
        return out

    def get_root_page(self):
        return self.pages[0]

    def page_name_from_url(self, path):
        path = os.path.splitext(os.path.basename(path))[0]
        name_str = re.sub(r'[-_]', ' ', path)
        return name_str.capitalize()

    def create_page(self, parent_page, file_path, name=None, type='ARTICLE'):
        path = os.path.basename(file_path)
        if not name:
            name = self.page_name_from_url(path)

        if self.dry_run:
            out = {
                "id": uuid.uuid4().int,
                "siteId": parent_page['siteId'],
                "parentPageId": parent_page['id'],
                "orderNumber": 0,
                "name": name,
                "displayedPath": '/' + self.absolute_url_from_path(file_path),
                "type": type,
                "state": "SKETCH",
                "futureVersionState": "NONE",
                "bip": False,
                "recommendedForMainSite": False,
                "showInSiteMenu": False,
                "createDate": "01.01.2026 00:00",
                "updateDate": "01.01.2026 00:00",
                "pages": [],
                "registers": []
            }
            parent_page['pages'].append(out)
        else:
            out = self.client.post_page(parent_page['id'], type, name, self.absolute_url_from_path(file_path))
            out['pages'] = []

        return out

    def refresh(self):
        self.pages = self.client.get_pages()

    def update_page(self, page_path):

        page_content = MarkdownParser(os.path.join(TRANSFORMED_DIR, page_path))

        page = self.find_page_for_path(page_path)
        page_id = page['id']
        page_versions = self.client.get_page_version_history(page_id)
        last_version = page_versions[0]
        last_version_path = str(last_version['version']['major'])+'/'+str(last_version['version']['minor'])
        if last_version['state'] == 'SKETCH':
            page_content = page_content.get_html()
            page_title = page_content.get_title()
            page_displayed_path = page['displayedPath'].strip('/')
            response = self.client.put_page_version(
                page_id, last_version_path, page_content, page_title, page_displayed_path
            )
            self.page_updates_logs.append({
                'request': {
                    'page_id': page_id,
                    'last_version_path': last_version_path,
                    'page_content': page_id,
                    'page_displayed_path': page_displayed_path,
                },
                'response': response
            })

class Publisher:

    def __init__(self):
        self.client = RedakcjaGovPlClient(config['site_id'], config['cookies'])
        self.pages_repository = PagesRepository()
        self.plan_content = []

    def walk_repo_folder(self, folder_id):
        """
        Recursively walk through repo folders and build a tree with folders and files.
        """

        def _walk(fid):
            results = self.client.get_repo_folders(fid)['results']
            for result in results:
                node = {
                    "folders": [],
                    "files": result.get("files", []),
                    "leadingPath": result.get("leadingPath", [])
                }
                for folder in result.get("folders", []):
                    child = _walk(folder["id"])
                    folder_node = dict(folder)
                    folder_node["children"] = child
                    node["folders"].append(folder_node)
            return node

        return _walk(folder_id)

    def refresh_repo_images(self):
        pass

    def refresh_repo_attachments(self):
        pass

    def load_index(self):
        with open(os.path.join(OUTPUT_DIR, "attachments.json"), "r", encoding="utf-8") as f:
            self.attachments = json.load(f)

        with open(os.path.join(OUTPUT_DIR, "images.json"), "r", encoding="utf-8") as f:
            self.images = json.load(f)

    def ensure_exists_page(self, file_path):
        if not file_path:
            return self.pages_repository.get_root_page()

        page = self.pages_repository.find_page_for_path(file_path)
        if page:
            return page

        parent_path = os.path.dirname(file_path)
        parent_page = self.pages_repository.find_page_for_path(parent_path)

        if not parent_page:
            parent_page = self.ensure_exists_page(parent_path)
        if not parent_page:
            parent_page = self.pages_repository.get_root_page()

        print(f"Create page: {file_path}")
        type = 'ARTICLE'
        if os.path.isdir(os.path.join(TRANSFORMED_DIR, file_path)):
            type = 'UNIVERSAL_LIST'
        out = self.pages_repository.create_page(parent_page, file_path, type=type)
        self.plan_content.append({'action': 'Create page', 'param': out})
        self.pages_repository.refresh()
        self.pages_repository.dump()
        return out

    def walk_pages(self):
        out = []
        for root, dirs, files in os.walk(TRANSFORMED_DIR):
            dirs.sort()
            files.sort()
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    out.append(os.path.relpath(file_path, TRANSFORMED_DIR))
        return out

    def execute(self):
        self.pages_repository.refresh()
        for page_path in tqdm(self.walk_pages(), desc="Ensure exists"):
            self.ensure_exists_page(page_path)

        for page_path in tqdm(self.walk_pages(), desc="Update page"):
            self.pages_repository.update_page(page_path)
        self.pages_repository.dump()
        self.dump_logs_updte_pages()
        self.dump_plan()

    def sort_pages(self):
        self.pages_repository.refresh()
        orders = []

        def sort_recursive(pages):
            sorted_pages = sorted(pages, key=lambda p: p.get("name", ""))
            for idx, page in enumerate(sorted_pages):
                orders.append((page["id"], idx, page["parentPageId"]))
                if "pages" in page and isinstance(page["pages"], list):
                    sort_recursive(page["pages"])
            # Reorder in-memory pages list to match sorted order
            pages[:] = sorted_pages

        sort_recursive(self.pages_repository.pages)
        for page_id, idx, parent_page_id in tqdm(orders):
            try:
                result = self.client.post_page_move(page_id, idx, parent_page_id)
            except Exception as e:
                print("Error: ", str(e))
        self.pages_repository.dump()

    def create_workspace(self):
        # shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    def test(self):
        # print(client.get_pages())
        # print(client.upload_image('741141c9-dc7f-4e8c-a4c4-883b496cd02a', 'faviconV3.png', 'test'))
        # print(client.put_page_sketch('21382036','2/0'))
        print(self.client.get_page_version_history('21382036'))

    def add_plan_step(self, param, out):
        self.plan_content.append({'action': param, 'param': out})

    def dump_plan(self):
        timestamp = int(time.time())
        with open(os.path.join(OUTPUT_DIR, f"plan.json"), "w", encoding="utf-8") as f:
            json.dump(self.plan_content, f, indent=2)

    def set_dry_run(self, dry_run=True):
        self.pages_repository.dry_run = dry_run

    def dump_logs_updte_pages(self):
        timestamp = int(time.time())
        with open(os.path.join(OUTPUT_DIR, f"update_pages_{timestamp}.json"), "w", encoding="utf-8") as f:
            json.dump(self.plan_content, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publisher CLI")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["create_index", "plan", "apply", "apply", "sort_pages", "test", "client"],
        help="Command to run"
    )

    # Subparsers for client command
    client_parser = argparse.ArgumentParser(add_help=False)
    client_subparsers = client_parser.add_subparsers(dest="client_command")

    get_repo_folder_parser = client_subparsers.add_parser("get_repo_folder")
    get_repo_folder_parser.add_argument("folder_id")

    delete_repo_folder_parser = client_subparsers.add_parser("delete_repo_folder")
    delete_repo_folder_parser.add_argument("folder_id")

    args, unknown = parser.parse_known_args()

    publisher = Publisher()
    publisher.create_workspace()

    if args.command == "test":
        publisher.test()
    elif args.command == "create_index":
        publisher.create_index()
    elif args.command == "plan":
        publisher.set_dry_run(True)
        publisher.execute()
    elif args.command == "apply":
        publisher.set_dry_run(False)
        publisher.execute()
    elif args.command == "sort_pages":
        publisher.set_dry_run(False)
        publisher.sort_pages()
    elif args.command == "client":
        # Parse subcommands for client
        client_args = client_parser.parse_args(unknown)
        if client_args.client_command == "get_repo_folder":
            resp = publisher.client.get_repo_folders(client_args.folder_id)
            print(f"Delete page {client_args.folder_id}: {resp}")
        elif client_args.client_command == "delete_repo_folder":
            resp = publisher.client.delete_repo_folder(client_args.folder_id)
            print(f"Delete repo folder {client_args.folder_id}: {resp}")
        else:
            print("No valid client subcommand provided.")
    else:
        publisher.create_index()
