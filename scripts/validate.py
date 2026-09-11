#!/usr/bin/env python3
"""校验技能包结构：frontmatter 必填字段、内部相对链接不死链、版本号一致。"""

import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_ROOT = os.path.join(ROOT, "plugins", "click")
SKILLS = [
    "plugins/click/skills/click-drama",
    "plugins/click/skills/click-media",
    "plugins/click/skills/click-assets",
]
REQUIRED_FIELDS = ["name", "description"]

errors = []


def fail(msg):
    errors.append(msg)


def rel(path):
    return os.path.relpath(path, ROOT)


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end == -1:
        return None
    body = text[4:end + 1]
    fields = {}
    current = None
    for number, line in enumerate(body.split("\n"), 1):
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$", line)
        if m:
            current = m.group(1)
            if current in fields:
                raise ValueError(f"frontmatter 重复字段 `{current}`")
            fields[current] = "" if m.group(2) in (None, "|") else m.group(2).strip()
            continue
        if line.startswith((" ", "\t")) and current:
            fields[current] = (fields[current] + "\n" + line.strip()).strip()
            continue
        raise ValueError(f"frontmatter 第 {number} 行不是支持的 YAML 格式")
    return fields


def check_frontmatter():
    for skill in SKILLS:
        path = os.path.join(ROOT, skill, "SKILL.md")
        if not os.path.isfile(path):
            fail(f"缺少 {skill}/SKILL.md")
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        try:
            fields = parse_frontmatter(text)
        except ValueError as exc:
            fail(f"{rel(path)}: {exc}")
            continue
        if fields is None:
            fail(f"{rel(path)}: 缺少 YAML frontmatter（--- 包裹）")
            continue
        for key in REQUIRED_FIELDS:
            if not fields.get(key):
                fail(f"{rel(path)}: frontmatter 缺少必填字段 `{key}`")
        extra = sorted(set(fields) - set(REQUIRED_FIELDS))
        if extra:
            fail(f"{rel(path)}: frontmatter 只允许 name/description，多出 {extra}")
        expected_name = os.path.basename(skill)
        if fields.get("name") != expected_name:
            fail(f"{rel(path)}: frontmatter name=`{fields.get('name')}`，应为 `{expected_name}`")
        if "NOT for" not in text[: text.find("\n---\n", 3)]:
            fail(f"{rel(path)}: description 缺少 `NOT for:` 路由说明")


LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def github_slug(text):
    text = text.strip().lower()
    text = re.sub(r"[^\w\-\u4e00-\u9fff ]", "", text)
    return re.sub(r"[ ]+", "-", text)


def markdown_anchors(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return {
        github_slug(match.group(1))
        for match in re.finditer(r"^#{1,6}\s+(.+?)\s*$", text, re.M)
    }


def check_links():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", ".github")]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for target in LINK_RE.findall(text):
                target = target.split()[0].strip()
                if re.match(r"^(https?:|mailto:|#)", target):
                    continue
                file_target, separator, anchor = target.partition("#")
                target = file_target
                if not target and not separator:
                    continue
                resolved = path if not target else os.path.normpath(os.path.join(dirpath, target))
                if not os.path.exists(resolved):
                    fail(f"{rel(path)}: 死链 `{target}`")
                elif anchor and os.path.isfile(resolved) and resolved.endswith(".md"):
                    decoded = urllib.parse.unquote(anchor).lower()
                    if decoded not in markdown_anchors(resolved):
                        fail(f"{rel(path)}: 不存在的 Markdown 锚点 `#{anchor}`")


def check_versions():
    version_file = os.path.join(ROOT, "VERSION")
    if not os.path.isfile(version_file):
        fail("缺少 VERSION")
        return
    with open(version_file, encoding="utf-8") as f:
        version = f.read().strip()
    semver = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
    if not re.fullmatch(semver, version):
        fail(f"VERSION 内容 `{version}` 不是语义化版本号")
        return

    for manifest in [
        "plugins/click/.claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        "plugins/click/.codex-plugin/plugin.json",
    ]:
        path = os.path.join(ROOT, manifest)
        if not os.path.isfile(path):
            fail(f"缺少 {manifest}")
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            fail(f"{manifest}: JSON 解析失败 —— {exc}")
            continue
        found = data.get("version")
        if found is None and isinstance(data.get("plugins"), list):
            found = next((p.get("version") for p in data["plugins"]), None)
        if found != version:
            fail(f"{manifest}: version=`{found}`，与 VERSION `{version}` 不一致")

    changelog = os.path.join(ROOT, "CHANGELOG.md")
    if not os.path.isfile(changelog):
        fail("缺少 CHANGELOG.md")
        return
    with open(changelog, encoding="utf-8") as f:
        heads = re.findall(rf"^## \[({semver})\]", f.read(), re.M)
    if not heads:
        fail("CHANGELOG.md: 找不到 `## [x.y.z]` 版本条目")
    elif heads[0] != version:
        fail(f"CHANGELOG.md: 最新条目 `{heads[0]}`，与 VERSION `{version}` 不一致")


def check_no_secrets():
    pattern = re.compile(r"cak_[A-Za-z0-9]{32,}")
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, IsADirectoryError):
                continue
            if pattern.search(text):
                fail(f"{rel(path)}: 疑似明文 API Key（cak_ + 48 位十六进制）")


def check_manifests():
    for manifest in [
        "plugins/click/.claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        ".agents/plugins/marketplace.json",
        "plugins/click/.codex-plugin/plugin.json",
    ]:
        path = os.path.join(ROOT, manifest)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            continue  # check_versions reports the precise parse error
        if manifest.endswith("marketplace.json"):
            if not data.get("name") or not isinstance(data.get("plugins"), list) or not data["plugins"]:
                fail(f"{manifest}: 需要非空 name 和 plugins")
        else:
            for field in ("name", "version", "description"):
                if not data.get(field):
                    fail(f"{manifest}: 缺少非空 `{field}`")
    codex = os.path.join(PLUGIN_ROOT, ".codex-plugin/plugin.json")
    if os.path.isfile(codex):
        with open(codex, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("skills") != "./skills/":
            fail("plugins/click/.codex-plugin/plugin.json: skills 必须指向 `./skills/`")
        allowed = {
            "name", "version", "description", "author", "homepage", "repository",
            "license", "keywords", "skills", "interface", "apps", "mcpServers",
        }
        extra = sorted(set(data) - allowed)
        if extra:
            fail(f"plugins/click/.codex-plugin/plugin.json: Codex 不支持字段 {extra}")

    marketplace = os.path.join(ROOT, ".agents/plugins/marketplace.json")
    if os.path.isfile(marketplace):
        with open(marketplace, encoding="utf-8") as f:
            data = json.load(f)
        entries = [item for item in data.get("plugins", []) if item.get("name") == "click"]
        if len(entries) != 1:
            fail(".agents/plugins/marketplace.json: 必须有且仅有一个 click 条目")
        else:
            entry = entries[0]
            if entry.get("source") != {"source": "local", "path": "./plugins/click"}:
                fail(".agents/plugins/marketplace.json: click source 必须指向 ./plugins/click")
            policy = entry.get("policy", {})
            if policy.get("installation") != "AVAILABLE" or policy.get("authentication") != "ON_INSTALL":
                fail(".agents/plugins/marketplace.json: click policy 不完整")

    skills_dir = os.path.join(PLUGIN_ROOT, "skills")
    if os.path.isdir(skills_dir):
        for name in os.listdir(skills_dir):
            path = os.path.join(skills_dir, name)
            if os.path.isdir(path) and not os.path.isfile(os.path.join(path, "SKILL.md")):
                fail(f"plugins/click/skills/{name}: skills 一级目录必须包含 SKILL.md")


def check_no_generated_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            if name.endswith(".pyc"):
                fail(f"{rel(os.path.join(dirpath, name))}: 不应提交 Python 编译产物")


def check_recovery_contract():
    path = os.path.join(PLUGIN_ROOT, "common/async-tasks.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    required = {
        "media_task": "/api/ai/tasks/",
        "auto_produce": "/api/storyboards/auto-produce",
        "shot_generation": "/scene-tasks",
        "episode_batch": "/episode-video-tasks",
        "review_asset": "/api/review-assets/",
    }
    for operation_type, endpoint in required.items():
        if operation_type not in text or endpoint not in text:
            fail(f"common/async-tasks.md: 恢复契约缺少 {operation_type} → {endpoint}")


def check_uploaded_asset_contract():
    required = {
        "plugins/click/common/upload.md": ["可选的管理步骤", "source=uploaded", "source=imported", "不查询对应的 media_asset"],
        "plugins/click/common/api-index.md": ["/api/media", "source=uploaded", "source=imported"],
        "plugins/click/skills/click-assets/SKILL.md": ["/api/media", 'source":"uploaded', "source=imported", "只保存引用"],
        "plugins/click/skills/click-media/SKILL.md": ["不需要先创建素材记录", "可选的管理步骤", "source=imported"],
        "plugins/click/skills/click-drama/references/stepwise.md": ["POST /api/media", "data.id", "referenceAssetIdList"],
    }
    for relative_path, markers in required.items():
        path = os.path.join(ROOT, relative_path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        missing = [marker for marker in markers if marker not in text]
        if missing:
            fail(f"{relative_path}: 上传素材登记契约缺少 {missing}")


def check_update_contract():
    checker = os.path.join(PLUGIN_ROOT, "common", "scripts", "check_version.py")
    guide = os.path.join(PLUGIN_ROOT, "common", "version-check.md")
    if not os.path.isfile(checker):
        fail("缺少 common/scripts/check_version.py")
    if not os.path.isfile(guide):
        fail("缺少 common/version-check.md")

    link = "[使用前版本检查](../../common/version-check.md)"
    for skill in SKILLS:
        path = os.path.join(ROOT, skill, "SKILL.md")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if link not in text:
            fail(f"{skill}/SKILL.md: 缺少共享使用前版本检查")


def main():
    check_frontmatter()
    check_links()
    check_versions()
    check_no_secrets()
    check_manifests()
    check_recovery_contract()
    check_uploaded_asset_contract()
    check_update_contract()
    check_no_generated_files()

    if errors:
        print("校验失败：")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("校验通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
