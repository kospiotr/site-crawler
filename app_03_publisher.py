import requests
import requests
import base64
import mimetypes
import json
import os

config = {
    'url': 'https://www.gov.pl/web/zsckr-zdunska-dabrowa',
    'site_id': '20003421',
    'repository':{
        'folder_root_id': '2c907143-e3cf-451b-ab0e-aa915030c43b',
        'folder_aktualnosci_id': '7fce3566-3f99-4679-bf42-c512652c0261',
    },
    'cookies': {
        # 'COOKIE_SUPPORT': 'true',
        # '_pk_id.1.0a22': '7d1f3ed8001d8e61.1771359373.',
        # 'mtm_cookie_consent': '1771359373448',
        'JSESSIONID': 'DDFB72C3EFED377A2AB62385CE235CD9',
        'XSRF-TOKEN': 'e0d0c21b-462a-4281-91dc-c09c0853684a',
        # '_pk_ses.1.0a22': '1',
        # 'gov-hamburger': 'no'
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
            f'{self.base_url}/api/v2/repo/folders/{parent_folder_id}',
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

if __name__ == "__main__":
    client = RedakcjaGovPlClient(config['site_id'], config['cookies'])
    # print(client.get_pages())
    # print(client.upload_image('741141c9-dc7f-4e8c-a4c4-883b496cd02a', 'faviconV3.png', 'test'))
    # print(client.put_page_sketch('21382036','2/0'))
    print(client.get_page_version_history('21382036'))