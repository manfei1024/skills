#!/usr/bin/env python3
"""Compare the installed Click plugin version with the main-branch manifest."""

import json
import pathlib
import re
import sys
import urllib.error
import urllib.request


PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCAL_MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
LATEST_MANIFEST_URL = (
    "https://raw.githubusercontent.com/manfei1024/skills/"
    "main/plugins/click/.codex-plugin/plugin.json"
)
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


class VersionCheckError(RuntimeError):
    pass


def manifest_version(payload: object, source: str) -> str:
    if not isinstance(payload, dict):
        raise VersionCheckError(f"{source} 不是 JSON 对象")
    version = payload.get("version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise VersionCheckError(f"{source} 缺少有效的语义化 version")
    return version


def read_local_version(path: pathlib.Path = LOCAL_MANIFEST) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionCheckError(f"无法读取本地版本：{exc}") from exc
    return manifest_version(payload, str(path))


def fetch_latest_version(url: str = LATEST_MANIFEST_URL, timeout: float = 10) -> str:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "click-skill-version-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, urllib.error.URLError) as exc:
        raise VersionCheckError(f"无法读取远端版本：{exc}") from exc
    return manifest_version(payload, url)


def main() -> int:
    try:
        current = read_local_version()
        latest = fetch_latest_version()
    except VersionCheckError as exc:
        print(f"Click skill 版本检查失败：{exc}", file=sys.stderr)
        return 2

    if current == latest:
        print(f"Click skill 已是最新版本 {current}")
        return 0

    print(f"Click skill 需要更新：本地 {current}，main {latest}")
    return 10


if __name__ == "__main__":
    sys.exit(main())
