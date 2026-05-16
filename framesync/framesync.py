#!/usr/bin/env python3
import base64
import tomllib
import requests
from pathlib import Path

API_V2  = "https://my.microsoftpersonalcontent.com/_api/v2.0"
API_V21 = "https://my.microsoftpersonalcontent.com/_api/v2.1"
APP_ID  = "00000000-0000-0000-0000-0000481710a4"

def get_badger_token() -> str:
    resp = requests.post("https://api-badgerp.svc.ms/v1.0/token",
        headers={"Content-Type": "application/json"},
        json={"appId": APP_ID})
    resp.raise_for_status()
    return resp.json()["token"]

def encode_url(url: str) -> str:
    return base64.b64encode(url.encode()).rstrip(b"=").decode().replace("/", "_").replace("+", "-")

def validate_password(encoded_url: str, share_url: str, password: str, token: str):
    url = f"{API_V21}/shares/u!{encoded_url}/root/oneDrive.validatePermission"
    challenge = base64.b64encode(share_url.encode()).decode()
    resp = requests.post(url,
        headers={
            "Authorization": f"Badger {token}",
            "Content-Type": "application/json",
        },
        json={"challengeToken": challenge, "password": password})
    if not resp.ok:
        print(f"Password validation failed {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    print("Password validated.")

def redeem_share(encoded_url: str, token: str) -> dict:
    url = f"{API_V2}/shares/u!{encoded_url}/driveitem"
    params = {"$select": "id,parentReference,folder,bundle,remoteItem,name,file,@content.downloadUrl"}
    resp = requests.post(url,
        headers={
            "Authorization": f"Badger {token}",
            "Prefer": "autoredeem",
            "Content-Type": "text/plain;charset=UTF-8",
        },
        params=params,
        data="")
    if not resp.ok:
        print(f"Redeem failed {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    return resp.json()

def sync_folder(drive_id: str, folder_id: str, token: str, dest: Path) -> list[Path]:
    """Sync a remote OneDrive folder into dest. Returns list of newly downloaded files."""
    dest.mkdir(parents=True, exist_ok=True)
    remote_names = set()
    new_files: list[Path] = []

    url = f"{API_V2}/drives/{drive_id}/items/{folder_id}/children"
    while url:
        resp = requests.get(url, headers={"Authorization": f"Badger {token}"})
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("value", []):
            name = item["name"]
            remote_names.add(name)
            if "file" in item:
                dest_file = dest / name
                if dest_file.exists():
                    print(f"  Skip: {name}")
                    continue
                print(f"  Downloading: {name}")
                dl_url = item.get("@content.downloadUrl")
                if not dl_url:
                    ir = requests.get(f"{API_V2}/drives/{drive_id}/items/{item['id']}",
                                      headers={"Authorization": f"Badger {token}"})
                    ir.raise_for_status()
                    dl_url = ir.json().get("@content.downloadUrl")
                r = requests.get(dl_url, stream=True)
                r.raise_for_status()
                with open(dest_file, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                new_files.append(dest_file)
            elif "folder" in item:
                print(f"  Entering: {name}")
                new_files.extend(sync_folder(drive_id, item["id"], token, dest / name))
        url = data.get("@odata.nextLink")

    # Delete local files/dirs not present remotely
    for local in dest.iterdir():
        if local.name not in remote_names:
            if local.is_file():
                print(f"  Deleting: {local.name}")
                local.unlink()
            elif local.is_dir():
                import shutil
                print(f"  Deleting dir: {local.name}")
                shutil.rmtree(local)

    return new_files

def main():
    with open(Path(__file__).parent / "config.toml", "rb") as f:
        config = tomllib.load(f)

    share_url = config["share_url"]
    password  = config["password"]
    dest_dir = Path(config["output_dir"])

    print("Getting Badger token...")
    token = get_badger_token()

    encoded = encode_url(share_url)

    print("Validating password...")
    validate_password(encoded, share_url, password, token)

    print("Redeeming share...")
    root = redeem_share(encoded, token)
    print(f"Root: {root.get('name')}")

    drive_id  = root["parentReference"]["driveId"]
    folder_id = root["id"]

    new_files: list[Path] = []

    if "file" in root:
        print(f"Downloading single file: {root['name']}")
        r = requests.get(root["@content.downloadUrl"], stream=True)
        r.raise_for_status()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / root["name"]
        with open(dest_file, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        new_files.append(dest_file)
    else:
        new_files = sync_folder(drive_id, folder_id, token, dest_dir)

    print("Done.")

    if new_files:
        print(f"Synced {len(new_files)} new file(s) — slideshow will pick them up on next cycle.")

if __name__ == "__main__":
    main()
