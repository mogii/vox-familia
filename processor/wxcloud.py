"""Minimal client for the WeChat 云开发 (CloudBase) server HTTP API.

Only needs the mini-program's AppID + AppSecret — no Tencent Cloud CAM keys.
Writes here run with admin rights, so they bypass the collection's security
rules (that's fine: only this script publishes).

Docs: https://developers.weixin.qq.com/miniprogram/dev/wxcloud/reference-http-api/
"""

import json
import time

import requests

BASE = "https://api.weixin.qq.com"
_token_cache = {"value": None, "expires_at": 0}


def get_access_token(appid, secret):
    now = time.time()
    if _token_cache["value"] and now < _token_cache["expires_at"]:
        return _token_cache["value"]

    r = requests.post(
        f"{BASE}/cgi-bin/stable_token",
        json={"grant_type": "client_credential", "appid": appid, "secret": secret},
        timeout=20,
    )
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"获取 access_token 失败：{data}")
    _token_cache["value"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 7200) - 120
    return data["access_token"]


def _check(data, what):
    if data.get("errcode", 0) not in (0, None):
        raise RuntimeError(f"{what} 失败：{data}")
    return data


def upload_file(token, env, cloud_path, local_path):
    """Upload one local image to cloud storage; return its fileID."""
    r = requests.post(
        f"{BASE}/tcb/uploadfile",
        params={"access_token": token},
        json={"env": env, "path": cloud_path},
        timeout=30,
    )
    meta = _check(r.json(), "申请上传链接")

    fields = [
        ("key", cloud_path),
        ("Signature", meta["authorization"]),
        ("x-cos-security-token", meta.get("token", "")),
        ("x-cos-meta-fileid", meta.get("cos_file_id", "")),
    ]
    with open(local_path, "rb") as fh:
        files = [(k, (None, v)) for k, v in fields]
        files.append(("file", ("file", fh, "application/octet-stream")))
        up = requests.post(meta["url"], files=files, timeout=120)
    if up.status_code not in (200, 204):
        raise RuntimeError(f"上传文件到存储失败 ({up.status_code})：{up.text[:300]}")
    return meta["file_id"]


def db_add(token, env, collection, records):
    """Insert records (list of dicts) into a collection; return inserted ids."""
    data_literal = json.dumps(records, ensure_ascii=False)
    query = f'db.collection("{collection}").add({{data: {data_literal}}})'
    r = requests.post(
        f"{BASE}/tcb/databaseadd",
        params={"access_token": token},
        json={"env": env, "query": query},
        timeout=30,
    )
    data = _check(r.json(), "写入数据库")
    return data.get("id_list", [])
