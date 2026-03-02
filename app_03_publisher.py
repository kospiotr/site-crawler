import argparse
import math
import re
import shutil
import time
import uuid
import yaml

import markdown
import requests
import base64
import mimetypes
import json
import os
import dataclasses

from PIL import Image

from tqdm import tqdm

from config import OUTPUT_DIR, TRANSFORMED_ASSETS_DIR
from config import TRANSFORMED_DIR

config = {
    'url': 'https://www.gov.pl/web/zsckr-zdunska-dabrowa',
    'site_id': '20003421',
    'repository': {
        'images_root_id': '2c907143-e3cf-451b-ab0e-aa915030c43b',
        'attachments_root_id': 'a7b3e0cf-d9d7-4182-8898-beb7807528a5',
    },
    'cookies': {
        'JSESSIONID': '0C917E91151C175F2981E5F9F16BE42D',
        'XSRF-TOKEN': '77784cc2-dd0c-4e38-89a9-3c7f0adf0c44',
    }
}


def index_decorator(name):
    timestamp = int(time.time())

    def decorator(cls):
        def load_from_file(self):
            try:
                with open(os.path.join(OUTPUT_DIR, f"{name}.json"), "r", encoding="utf-8") as f:
                    self.index_content = json.load(f)
            except Exception as e:
                self.index_content = []

        def dump(self):
            with open(os.path.join(OUTPUT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
                json.dump(self.index_content, f, indent=2)

        def refresh(self):
            pass

        def ensure_index_loaded(self):
            if not self.index_content:
                print(f"Loading index from file: {name}.json")
                self.load_from_file()

        cls.load_from_file = load_from_file
        cls.dump = dump
        cls.index_content = []
        if not cls.refresh:
            cls.refresh = refresh

        cls.ensure_index_loaded = ensure_index_loaded
        return cls

    return decorator


def dumper_decorator(name: str, timestamp: bool = False):
    timestamp = int(time.time())

    def decorator(cls):
        data_key = f'__dump_{name}_content'

        def dump(self):
            file_name = f"{name}.json" if not timestamp else f"{name}_{timestamp}.json"
            with open(os.path.join(OUTPUT_DIR, file_name), "w", encoding="utf-8") as f:
                json.dump(getattr(cls, data_key), f, indent=2)

        def add(self, value):
            getattr(cls, data_key).append(value)

        setattr(cls, data_key, [])
        setattr(cls, f'add_{name}', add)
        setattr(cls, f'dump_{name}', dump)
        return cls

    return decorator

@dataclasses.dataclass
class Asset:
    url: str
    metas: list[str]
    ext: str
    rel_path: str
    page_title: str

    def get_description(self):
        return self.page_title

class PageContent:

    def __init__(self, file_path):
        with open(file_path, encoding="utf-8") as f:
            self.raw_content = f.read()

        self.file_path = file_path
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

    def get_asset_file_path(self, page_file_path, resource_path):
        base_dir = os.path.dirname(page_file_path)
        assets_path = os.path.normpath(os.path.join(base_dir, resource_path))
        return os.path.relpath(assets_path, TRANSFORMED_ASSETS_DIR)

    def extract_assets(self):
        out = []
        assets = self.frontmatter.get("assets", [])

        for asset_url, asset_metas in assets.items():
            out.append(Asset(
                url=asset_url,
                metas=asset_metas,
                ext=os.path.splitext(asset_url)[1],
                rel_path=self.get_asset_file_path(self.file_path, asset_url),
                page_title=self.get_title()
            ))

        return out

    def get_images(self):
        out = []
        for asset in self.extract_assets():
            if asset.ext in ['.jpg', '.jpe', '.jpeg', '.png', '.gif', '.svg', '.bmp', '.webp', '.ico']:
                out.append(asset)
        return out


    def get_attachments(self):
        out = []
        for asset in self.extract_assets():
            if asset.ext not in ['.jpg', '.jpe', '.jpeg', '.png', '.gif', '.svg', '.bmp', '.webp', '.ico']:
                out.append(asset)
        return out


class ApiResponseException(Exception):
    def __init__(self, status_code, payload):
        super().__init__(f"API returned status {status_code}: {payload}")
        self.status_code = status_code
        self.payload = payload


class RedakcjaGovPlClient:
    base_url: str = 'https://redakcja.www.gov.pl'
    site_id: str = None
    session = requests.Session()
    cookies: dict[str, str] = []

    def __init__(self, site_id: str, cookies: dict[str, str]):
        self.site_id = site_id
        self.cookies = cookies

    def _handle_response(self, response):
        if response.status_code != 200:
            try:
                payload = response.json()
            except Exception:
                payload = response.text
            raise ApiResponseException(response.status_code, payload)
        return response.json()

    def get_pages(self):
        response = requests.get(
            f'{self.base_url}/api/v2/sites/{self.site_id}/pages?',
            headers={
                'accept': 'application/json, text/plain, */*',
            },
            cookies=self.cookies
        )
        return self._handle_response(response)

    def post_page(self, parent_page_id: str, type: str, name: str, displayed_path: str):
        displayed_path = displayed_path.removeprefix('/')
        response = requests.post(
            f'{self.base_url}/api/v2/sites/{self.site_id}/pages?parentPageId={parent_page_id}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies,
            json={"pages": [], "registers": [], "renderChildrenComponents": False, "isAccessPermited": False,
                  "type": type, "showInSiteMenu": True, "name": name,
                  "displayedPath": displayed_path}
        )
        return self._handle_response(response)

    def post_page_move(self, page_id: str, order_number: int, parent_page_id):
        response = requests.post(
            f'{self.base_url}/api/v2/pages/{page_id}/translations/pl_PL/move/{parent_page_id}/{order_number}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies
        )
        return self._handle_response(response)

    def get_repo_folders_page(self, parent_folder_id: str, page = None):
        if not page:
            page = 1

        response = requests.get(
            f'{self.base_url}/api/v2/repo/folders/{parent_folder_id}/content?query=&name=&sort=createDate,desc&page={page}&size=100&deep=false&extension=',
            headers={
                'accept': 'application/json, text/plain, */*',
            },
            cookies=self.cookies
        )
        return self._handle_response(response)

    def get_repo_folders(self, parent_folder_id: str):
        first_page = self.get_repo_folders_page(parent_folder_id)
        total = int(first_page['total'])
        pages = math.ceil(total / 100)
        for page in range(2, pages + 1):
            n_page = self.get_repo_folders_page(parent_folder_id, page)
            first_page['results'][0]['folders'].extend(n_page['results'][0]['folders'])
            first_page['results'][0]['files'].extend(n_page['results'][0]['files'])

        return first_page

    def create_repo_folder(self, parent_folder_id: str, name: str):
        response = requests.post(
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
        )
        return self._handle_response(response)

    def delete_repo_folder(self, folder_id: str):
        response = requests.delete(
            f'{self.base_url}/api/v2/repo/folders/{folder_id}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'content-type': 'application/json',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies
        )
        if response.status_code != 200:
            try:
                payload = response.json()
            except Exception:
                payload = response.text
            raise ApiResponseException(response.status_code, payload)
        return response

    def upload_image(self, folder_id, file_path, description):
        # Guess the mime type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        width = 64
        height = 64
        with Image.open(file_path) as img:
            width, height = img.size

        # Read and encode file
        with open(file_path, 'rb') as f:
            file_bytes = f.read()
            encoded = base64.b64encode(file_bytes).decode('utf-8')

        # Prepare metadata
        metadata = {
            "folderId": folder_id,
            "hidden": False,
            "width": width,  # Set actual width if needed
            "height": height,  # Set actual height if needed
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
        return self._handle_response(response)

    def put_page_sketch(self, page_id: str, from_version: str):
        response = requests.put(
            f'{self.base_url}/api/v2/page/{page_id}/from/version/{from_version}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies
        )
        return self._handle_response(response)

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
        response = requests.put(
            f'{self.base_url}/api/v2/page/{page_id}/version/{from_version}',
            headers={
                'accept': 'application/json, text/plain, */*',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies,
            json=request_body
        )
        return self._handle_response(response)

    def get_page_version_history(self, page_id: str):
        response = requests.get(
            f'{self.base_url}/api/v2/page/{page_id}/version-history',
            headers={
                'accept': 'application/json, text/plain, */*',
                'content-type': 'application/json',
                'x-xsrf-token': self.cookies['XSRF-TOKEN']
            },
            cookies=self.cookies
        )
        return self._handle_response(response)


@index_decorator("pages")
class PagesRepository:
    dry_run = True

    def __init__(self):
        self.client = RedakcjaGovPlClient(config['site_id'], config['cookies'])
        self.page_updates_logs = []

    def refresh(self):
        self.index_content = self.client.get_pages()
        self.dump()

    @staticmethod
    def nested_url_from_path(rel_path):
        return os.path.splitext(rel_path)[0]

    @staticmethod
    def absolute_url_from_path(rel_path):
        path_no_ext = os.path.splitext(rel_path)[0]
        url = re.sub(r'[^a-zA-Z0-9_-]', '-', path_no_ext)
        return url

    def find_page(self, path, pages=None):
        self.ensure_index_loaded()
        if not path:
            return None
        if not pages:
            pages = self.index_content

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
        return self.index_content[0]

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

    def update_page(self, page_path):

        page_content = PageContent(os.path.join(TRANSFORMED_DIR, page_path))

        page = self.find_page_for_path(page_path)
        page_id = page['id']
        page_versions = self.client.get_page_version_history(page_id)
        last_version = page_versions[0]
        last_version_path = str(last_version['version']['major']) + '/' + str(last_version['version']['minor'])
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


class ResourceRepository:

    def __init__(self, root_folder_id, dry_run=True):
        self.root_folder_id = root_folder_id
        self.dry_run = dry_run
        self.client = RedakcjaGovPlClient(config['site_id'], config['cookies'])
        self.index_content = []
        self.ensure_index_loaded()

    def walk_repo_folder(self, folder_id):
        """
        Recursively walk through repo folders and build a tree with folders and files.
        """

        def _walk(parent_folder_id, parent_folder_node):
            result = self.client.get_repo_folders(parent_folder_id)['results'][0]
            for folder in result.get("folders", []):
                folder_id = folder["id"]
                folder_name = folder["name"]

                folder_node = {"id": folder_id, "parentId": parent_folder_id, "name": folder_name, "folders": []}
                parent_folder_node["folders"].append(folder_node)
                _walk(folder["id"], folder_node)

            parent_folder_node['files'] = result["files"]

            return parent_folder_node

        return _walk(folder_id, {"id": folder_id, "parentId": None, "name": None, "folders": []})

    def get_root_folder(self):
        return self.index_content

    def find_folder_by_path(self, file_path, parent_folder=None):
        if not file_path:
            return None

        parts = os.path.normpath(file_path).split(os.sep)
        root_folder = parts[0]

        if not parent_folder:
            parent_folder = self.get_root_folder()

        children_folders = parent_folder['folders']

        for children_folder in children_folders:
            if children_folder["name"] == root_folder:
                if len(parts) == 1:
                    return children_folder
                return self.find_folder_by_path(os.sep.join(parts[1:]), children_folder)

        return None

    def find_file_by_path(self, file_path, parent_folder=None):
        if not file_path:
            return None
        file_folder = os.path.dirname(file_path)
        folder = self.find_folder_by_path(file_folder)
        if not folder:
            raise f'File folder does not exist for file: {file_path}'

        for file in folder['files']:
            if file['name'] == os.path.basename(file_path):
                return file
        return None



    def ensure_folder(self, folder_path):
        if folder_path in ['', '/', '.']:
            return

        if not self.find_folder_by_path(folder_path):
            parent_path = os.path.dirname(folder_path)
            folder_name = os.path.basename(folder_path)
            if parent_path == '':
                parent_folder = self.get_root_folder()
            else:
                parent_folder = self.find_folder_by_path(parent_path)

            if parent_folder:
                parent_folder_id = parent_folder["id"]
                print(
                    f"Creating folder: {folder_path} with parent: {parent_folder['name']} for repo: {self.root_folder_id}")
                new_folder = self.client.create_repo_folder(parent_folder_id, folder_name)
                parent_folder['folders'].append({
                    "name": folder_name,
                    "id": new_folder["id"],
                    "parentId": parent_folder_id,
                    "folders": [],
                    "files": []
                })
                self.dump()
            else:
                self.ensure_folder(parent_path)
        # else:
        #     print(f"Folder already exists: {folder_path} in repo: {self.root_folder_id}")

    def ensure_folders(self, assets):
        folders = set()
        for asset_rel_path, asset_path, asset_metas, page_content in assets:
            folder_path = os.path.dirname(asset_rel_path)
            parts = os.path.normpath(folder_path).split(os.sep)
            for i in range(1, len(parts) + 1):
                folder = os.path.join(*parts[:i])
                folders.add(folder)

        for folder_path in tqdm(folders, desc="Ensure folders"):
            self.ensure_folder(folder_path)


@index_decorator("repo-images")
class ImagesRepository(ResourceRepository):

    def __init__(self):
        super().__init__(config['repository']['images_root_id'])
        self.content = None

    def refresh(self):
        self.index_content = super().walk_repo_folder(self.root_folder_id)
        self.dump()


@index_decorator("repo-attachments")
class AttachmentsRepository(ResourceRepository):

    def __init__(self):
        super().__init__(config['repository']['attachments_root_id'])
        self.content = None

    def refresh(self):
        self.index_content = super().walk_repo_folder(self.root_folder_id)
        self.dump()


class LocalAssetsRepository:

    def __init__(self, pages_repository: PagesRepository, images_repository: ImagesRepository,
                 attachments_repository: AttachmentsRepository):
        self.pages_repository = pages_repository
        self.images_repository = images_repository
        self.attachments_repository = attachments_repository

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

    def parsing_pages(self) -> list[tuple[str, PageContent]]:
        out = []
        for page_path in tqdm(self.walk_pages(), desc="Parsing local pages"):
            page_content = PageContent(os.path.join(TRANSFORMED_DIR, page_path))
            out.append((page_path, page_content))
        return out


@dumper_decorator('publishing')
class Publisher:

    def __init__(self):
        self.client = RedakcjaGovPlClient(config['site_id'], config['cookies'])
        self.pages_repository = PagesRepository()
        self.images_repository = ImagesRepository()
        self.attachments_repository = AttachmentsRepository()
        self.local_resources_repository = LocalAssetsRepository(
            self.pages_repository,
            self.images_repository,
            self.attachments_repository
        )
        self.plan_content = []

    def refresh(self):
        print("Refresh pages index")
        self.pages_repository.refresh()
        print("Refresh images index")
        self.images_repository.refresh()
        print("Refresh attachment index")
        self.attachments_repository.refresh()

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

    def extract_images(self, parsed_local_pages):
        out = []
        for page_path, page_content in tqdm(parsed_local_pages, desc="Extracting images"):
            assets = page_content.get_images()
            for asset in assets:
                out.append(asset)
        return out

    def extract_attachments(self, parsed_local_pages):
        out = []
        for page_path, page_content in tqdm(parsed_local_pages, desc="Extracting attachments"):
            assets = page_content.get_attachments()
            out.append(assets)
        return out

    def upload_images(self, images):
        exists = []
        not_exists: list[Asset] = []
        visited = set([])
        for asset in tqdm(images, desc="Upload images"):
            if asset.rel_path in visited:
                continue

            repo_asset = self.images_repository.find_file_by_path(asset.rel_path)
            if repo_asset:
                exists.append(repo_asset)
                visited.add(asset.rel_path)
                continue

            repo_parent_folder = self.images_repository.find_folder_by_path(os.path.dirname(asset.rel_path))
            if not repo_parent_folder:
                raise f'Parent folder not found for asset: {asset}'

            not_exists.append((repo_parent_folder['id'], asset))
            visited.add(asset.rel_path)

        print(f'Exsists: {len(exists)}, Not exists: {len(not_exists)}')

        for parent_folder_id, not_exist_asset in tqdm(not_exists, desc="Uploading images"):
            file_path = os.path.join(TRANSFORMED_ASSETS_DIR, not_exist_asset.rel_path)
            try:
                self.client.upload_image(parent_folder_id, file_path, not_exist_asset.get_description())
            except Exception as e:
                self.add_publishing(('image upload error', file_path, str(e)))
                self.dump_publishing()


    def execute(self):
        self.refresh()
        for page_path in tqdm(self.local_resources_repository.walk_pages(), desc="Ensure page exists"):
            self.ensure_exists_page(page_path)

        parsed_local_pages = self.local_resources_repository.parsing_pages()

        images = self.extract_images(parsed_local_pages)
        # self.images_repository.ensure_folders(images)
        self.upload_images(images)
        #
        # attachments = self.extract_attachments(parsed_local_pages)
        # self.attachments_repository.ensure_folders(attachments)

        #
        # for page_path, page_content in tqdm(parsed_local_pages, desc="Update page"):
        #     self.pages_repository.update_page(page_path)
        # self.pages_repository.dump()
        # self.dump_logs_updte_pages()
        # self.dump_plan()

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
        # print(self.client.get_page_version_history('21382036'))
        print('Repo paginate folder: ', len(self.client.get_repo_folders('54ca33f1-2931-4beb-b40d-0d978b3735dd')))

    def add_plan_step(self, param, out):
        self.plan_content.append({'action': param, 'param': out})

    def dump_plan(self):
        timestamp = int(time.time())
        with open(os.path.join(OUTPUT_DIR, f"plan.json"), "w", encoding="utf-8") as f:
            json.dump(self.plan_content, f, indent=2)

    def set_dry_run(self, dry_run=True):
        self.pages_repository.dry_run = dry_run
        self.images_repository.dry_run = dry_run
        self.attachments_repository.dry_run = dry_run

    def dump_logs_updte_pages(self):
        timestamp = int(time.time())
        with open(os.path.join(OUTPUT_DIR, f"update_pages_{timestamp}.json"), "w", encoding="utf-8") as f:
            json.dump(self.plan_content, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publisher CLI")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["refresh", "plan", "apply", "apply", "sort_pages", "test", "client"],
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
    elif args.command == "refresh":
        publisher.refresh()
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
