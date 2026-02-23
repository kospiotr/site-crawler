import argparse
import shutil

import requests
import requests
import base64
import mimetypes
import json
import os

from config import OUTPUT_DIR

config = {
    'url': 'https://www.gov.pl/web/zsckr-zdunska-dabrowa',
    'site_id': '20003421',
    'repository':{
        'images_root_id': '2c907143-e3cf-451b-ab0e-aa915030c43b',
        'attachments_root_id': 'a7b3e0cf-d9d7-4182-8898-beb7807528a5',
        'folder_aktualnosci_id': '7fce3566-3f99-4679-bf42-c512652c0261',
    },
    'cookies': {
        'JSESSIONID': '6D86BCBCCDFFCFE0CC0089995B4E9819',
        'XSRF-TOKEN': '67083032-bd16-4e2a-b04f-febecbdb333f',
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

    # def walk(self, acc, fn):


    def refresh_pages(self):
        images = self.walk_repo_folder(config['repository']['images_root_id'])
        with open(os.path.join(OUTPUT_DIR, 'images.json'), "w", encoding="utf-8") as f:
            json.dump(images, f, indent=2)

        attachments = self.walk_repo_folder(config['repository']['attachments_root_id'])
        with open(os.path.join(OUTPUT_DIR, 'attachments.json'), "w", encoding="utf-8") as f:
            json.dump(attachments, f, indent=2)

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
        choices=["refresh", "plan", "apply", "test", "client"],
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
        publisher.refresh_pages()
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
        publisher.refresh_pages()
