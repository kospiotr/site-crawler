import argparse
import shutil

import requests
import requests
import base64
import mimetypes
import json
import os

from config import OUTPUT_DIR
from config import TRANSFORMED_DIR

config = {
    'url': 'https://www.gov.pl/web/zsckr-zdunska-dabrowa',
    'site_id': '20003421',
    'repository':{
        'images_root_id': '2c907143-e3cf-451b-ab0e-aa915030c43b',
        'attachments_root_id': 'a7b3e0cf-d9d7-4182-8898-beb7807528a5',
    },
    'cookies': {
        'JSESSIONID': 'C2136B4F4F833E53B9D11A9E8154856E',
        'XSRF-TOKEN': 'a6625cba-eea3-467f-9edb-f7cb15fc9a84',
    }
}


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
            "height": 64, # Set actual height if needed
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


class Publisher:

    def __init__(self):
        self.client = RedakcjaGovPlClient(config['site_id'], config['cookies'])

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
        """
        Loads and flattens indexes for images, pages, and attachments.
        Each index is a dict with the full path as the key.
        """
        def walk_folders_tree(tree, parent_path=""):
            index = {}
            # Handle files at this level
            for file in tree.get("files", []):
                path = os.path.join(parent_path, file["name"])
                index[path] = file
            # Handle folders recursively
            for folder in tree.get("folders", []):
                folder_path = os.path.join(parent_path, folder["name"])
                # Some trees (like images.json) have 'children' key for subfolders/files
                children = folder.get("children")
                if children:
                    index.update(walk_folders_tree(children, folder_path))
            return index

        # Images index
        with open(os.path.join(OUTPUT_DIR, "images.json"), "r", encoding="utf-8") as f:
            images_tree = json.load(f)
        self.images_index = walk_folders_tree(images_tree)

        # Attachments index
        with open(os.path.join(OUTPUT_DIR, "attachments.json"), "r", encoding="utf-8") as f:
            attachments_tree = json.load(f)
        self.attachments_index = walk_folders_tree(attachments_tree)

        # Pages index (flatten tree, key is displayedPath)
        def walk_pages_tree(pages, index={}):
            for page in pages:
                path = page.get("displayedPath")
                if path:
                    index[path] = page
                if "pages" in page:
                    walk_pages_tree(page["pages"], index)
            return index

        with open(os.path.join(OUTPUT_DIR, "pages.json"), "r", encoding="utf-8") as f:
            pages_tree = json.load(f)
        self.pages_index = walk_pages_tree(pages_tree)

    def get_page_by_path(self, relative_path):
        pass

    def plan(self):
        """
        Walk all markdown files from the transformed folder, read and print their content.
        """

        self.load_index()
        print(self.pages_index)

        for root, dirs, files in os.walk(TRANSFORMED_DIR):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.join('/',os.path.relpath(os.path.splitext(file_path)[0], TRANSFORMED_DIR))

                    if self.page_exists(relative_path):
                        pass
                    else:
                        pass
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        print(f"--- {file_path} {relative_path} ---")

    def create_index(self):

        pages = self.client.get_pages()
        with open(os.path.join(OUTPUT_DIR, 'pages.json'), "w", encoding="utf-8") as f:
            json.dump(pages, f, indent=2)
        #
        # images = self.walk_repo_folder(config['repository']['images_root_id'])
        # with open(os.path.join(OUTPUT_DIR, 'images.json'), "w", encoding="utf-8") as f:
        #     json.dump(images, f, indent=2)
        #
        # attachments = self.walk_repo_folder(config['repository']['attachments_root_id'])
        # with open(os.path.join(OUTPUT_DIR, 'attachments.json'), "w", encoding="utf-8") as f:
        #     json.dump(attachments, f, indent=2)

    def create_workspace(self):
        # shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    def test(self):
        # print(client.get_pages())
        # print(client.upload_image('741141c9-dc7f-4e8c-a4c4-883b496cd02a', 'faviconV3.png', 'test'))
        # print(client.put_page_sketch('21382036','2/0'))
        print(self.client.get_page_version_history('21382036'))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publisher CLI")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["create_index", "plan", "apply", "test", "client"],
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
        publisher.plan()
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
