import requests
import base64
import os

def upload_image_to_github(file, folder):

    token = os.environ.get("GITHUB_TOKEN")
    username = os.environ.get("GITHUB_USERNAME")
    repo = os.environ.get("GITHUB_REPO")

    file_content = base64.b64encode(file.read()).decode("utf-8")

    file_name = file.name

    url = f"https://api.github.com/repos/{username}/{repo}/contents/{folder}/{file_name}"

    headers = {
        "Authorization": f"token {token}"
    }

    data = {
        "message": f"upload {file_name}",
        "content": file_content
    }

    response = requests.put(url, json=data, headers=headers)

    if response.status_code == 201:

        cdn_url = f"https://cdn.jsdelivr.net/gh/{username}/{repo}/{folder}/{file_name}"

        return cdn_url

    return None