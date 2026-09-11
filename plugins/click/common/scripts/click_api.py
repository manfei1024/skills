#!/usr/bin/env python3
"""Small, dependency-free Click HTTP and recovery-state helper."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


KEY_RE = re.compile(r"cak_[0-9a-fA-F]{48}")
TERMINAL_STATUSES = {"completed", "failed", "succeeded", "approved"}
DEFAULT_CLICK_HOST = "https://click.vibehub.art"


class ClickError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        raise ClickError(f"拒绝 HTTP 重定向：{code} {newurl}")


def configured_host() -> str:
    """Use the public API by default, but never hide an invalid explicit override."""
    raw = os.environ["CLICK_HOST"] if "CLICK_HOST" in os.environ else DEFAULT_CLICK_HOST
    return validate_host(raw)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def redact(value: str) -> str:
    return KEY_RE.sub("cak_[REDACTED]", value)


def validate_host(raw: str) -> str:
    parsed = urllib.parse.urlsplit(raw)
    if not parsed.hostname or parsed.username or parsed.password:
        raise ClickError("CLICK_HOST 必须是无用户名/密码的绝对主机地址")
    loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise ClickError("CLICK_HOST 公网地址必须使用 https；仅 localhost/127.0.0.1/::1 可使用 http")
    if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ClickError("CLICK_HOST 不能包含路径、查询参数或 fragment")
    return raw.rstrip("/")


def validate_api_path(path: str) -> str:
    parsed = urllib.parse.urlsplit(path)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/api/"):
        raise ClickError("请求目标必须是以 /api/ 开头的相对路径")
    return path


def read_json_argument(raw: str | None, file_path: str | None) -> Any:
    if raw and file_path:
        raise ClickError("--json 和 --json-file 只能使用一个")
    if file_path:
        with open(file_path, encoding="utf-8") as handle:
            return json.load(handle)
    if raw:
        return json.loads(raw)
    return None


def request_json(
    method: str,
    path: str,
    body: Any = None,
    *,
    anonymous: bool = False,
    timeout: float = 60,
) -> Any:
    host = configured_host()
    path = validate_api_path(path)
    headers = {"Accept": "application/json"}
    if not anonymous:
        key = os.environ.get("CLICK_API_KEY", "")
        if not KEY_RE.fullmatch(key):
            raise ClickError("CLICK_API_KEY 缺失或格式不正确")
        headers["Authorization"] = f"Bearer {key}"
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(host + path, data=data, headers=headers, method=method)
    hostname = urllib.parse.urlsplit(host).hostname
    handlers = [NoRedirect]
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise ClickError(f"HTTP {exc.code}: {redact(raw)[:1000]}") from None
    except urllib.error.URLError as exc:
        raise ClickError(f"网络请求失败：{redact(str(exc.reason))}") from None
    if not 200 <= status < 300:
        raise ClickError(f"HTTP {status}: {redact(raw)[:1000]}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise ClickError(f"服务端没有返回 JSON：{redact(raw)[:500]}") from None
    if isinstance(payload, dict) and payload.get("code") not in (None, 0):
        code = payload.get("code")
        stable = payload.get("error_code") or payload.get("errorCode") or payload.get("message")
        raise ClickError(f"Click 业务错误 {code}: {redact(str(stable))}")
    return payload


def extract(payload: Any, dotted_path: str) -> Any:
    value = payload
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ClickError(f"响应缺少必需字段：{dotted_path}")
        value = value[part]
    if value in (None, ""):
        raise ClickError(f"响应字段为空：{dotted_path}")
    return value


def atomic_write(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def load_state(path: pathlib.Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            state = json.load(handle)
    except FileNotFoundError:
        raise ClickError(f"状态文件不存在：{path}") from None
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise ClickError("状态文件 schema_version 不受支持")
    state.setdefault("resources", {})
    state.setdefault("operations", [])
    return state


def confirmation_hash(body: Any, estimated_credits: str) -> str:
    canonical = json.dumps(
        {"body": body, "estimated_credits": estimated_credits},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def command_request(args: argparse.Namespace) -> None:
    body = read_json_argument(args.json, args.json_file)
    payload = request_json(args.method, args.path, body, anonymous=args.anonymous, timeout=args.timeout)
    if args.expect:
        for field in args.expect:
            extract(payload, field)
    if args.extract:
        output = extract(payload, args.extract)
    else:
        output = payload
    print(json.dumps(output, ensure_ascii=False))


def command_submit(args: argparse.Namespace) -> None:
    """Submit a mutation and persist its recovery record before returning."""
    body = read_json_argument(args.json, args.json_file)
    payload = request_json(args.method, args.path, body, timeout=args.timeout)
    operation_id = str(extract(payload, args.id_field))
    poll_path = args.poll_path.replace("{operation_id}", urllib.parse.quote(operation_id, safe=""))
    validate_api_path(poll_path)
    state_path = pathlib.Path(args.state)
    state = load_state(state_path)
    if any(op.get("operation_id") == operation_id for op in state["operations"]):
        raise ClickError(f"operation_id 已记录，拒绝重复：{operation_id}")
    scope = json.loads(args.scope)
    if not isinstance(scope, dict):
        raise ClickError("--scope 必须是 JSON object")
    for mapping in args.resource or []:
        name, separator, field = mapping.partition("=")
        if not separator or not name:
            raise ClickError("--resource 必须是 name=response.path")
        state["resources"][name] = str(extract(payload, field))
    state["operations"].append(
        {
            "operation_id": operation_id,
            "operation_type": args.operation_type,
            "poll_path": poll_path,
            "scope": scope,
            "status": "submitted",
            "submitted_at": now_iso(),
            "updated_at": now_iso(),
            "estimated_credits": args.estimated_credits,
            "confirmation_hash": confirmation_hash(body, args.estimated_credits),
        }
    )
    state["updated_at"] = now_iso()
    atomic_write(state_path, state)
    print(json.dumps({"operation_id": operation_id}, ensure_ascii=False))


def command_state_init(args: argparse.Namespace) -> None:
    path = pathlib.Path(args.file)
    if path.exists() and not args.force:
        raise ClickError(f"状态文件已存在：{path}；拒绝覆盖")
    host = configured_host()
    atomic_write(
        path,
        {
            "schema_version": 1,
            "project_name": args.project_name,
            "host": host,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "current_stage": "initialized",
            "resources": {},
            "operations": [],
        },
    )


def command_state_set(args: argparse.Namespace) -> None:
    path = pathlib.Path(args.file)
    state = load_state(path)
    target = state["resources"] if args.resource else state
    key, separator, value = args.value.partition("=")
    if not separator or not key:
        raise ClickError("值必须是 key=value")
    target[key] = value
    state["updated_at"] = now_iso()
    atomic_write(path, state)


def command_record_operation(args: argparse.Namespace) -> None:
    path = pathlib.Path(args.file)
    state = load_state(path)
    if any(op.get("operation_id") == args.operation_id for op in state["operations"]):
        raise ClickError(f"operation_id 已记录，拒绝重复：{args.operation_id}")
    body = read_json_argument(args.json, args.json_file)
    scope = json.loads(args.scope)
    if not isinstance(scope, dict):
        raise ClickError("--scope 必须是 JSON object")
    validate_api_path(args.poll_path)
    state["operations"].append(
        {
            "operation_id": args.operation_id,
            "operation_type": args.operation_type,
            "poll_path": args.poll_path,
            "scope": scope,
            "status": args.status,
            "submitted_at": now_iso(),
            "updated_at": now_iso(),
            "estimated_credits": args.estimated_credits,
            "confirmation_hash": confirmation_hash(body, args.estimated_credits),
        }
    )
    state["updated_at"] = now_iso()
    atomic_write(path, state)


def command_update_operation(args: argparse.Namespace) -> None:
    path = pathlib.Path(args.file)
    state = load_state(path)
    matches = [op for op in state["operations"] if op.get("operation_id") == args.operation_id]
    if len(matches) != 1:
        raise ClickError(f"operation_id 应唯一存在：{args.operation_id}")
    matches[0]["status"] = args.status
    matches[0]["updated_at"] = now_iso()
    if args.result_url:
        matches[0]["result_url"] = args.result_url
    state["updated_at"] = now_iso()
    atomic_write(path, state)


def command_pending(args: argparse.Namespace) -> None:
    state = load_state(pathlib.Path(args.file))
    pending = [op for op in state["operations"] if op.get("status") not in TERMINAL_STATUSES]
    print(json.dumps(pending, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)

    request = sub.add_parser("request", help="发送一个安全的 JSON API 请求")
    request.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    request.add_argument("path")
    request.add_argument("--json")
    request.add_argument("--json-file")
    request.add_argument("--anonymous", action="store_true")
    request.add_argument("--timeout", type=float, default=60)
    request.add_argument("--expect", action="append")
    request.add_argument("--extract")
    request.set_defaults(func=command_request)

    submit = sub.add_parser("submit", help="提交请求并在返回前原子记录恢复信息")
    submit.add_argument("method", choices=["POST", "PUT", "PATCH", "DELETE"])
    submit.add_argument("path")
    submit.add_argument("--state", required=True)
    submit.add_argument("--operation-type", required=True)
    submit.add_argument("--id-field", required=True)
    submit.add_argument("--poll-path", required=True)
    submit.add_argument("--scope", required=True)
    submit.add_argument("--estimated-credits", default="unknown")
    submit.add_argument("--json")
    submit.add_argument("--json-file")
    submit.add_argument("--resource", action="append")
    submit.add_argument("--timeout", type=float, default=60)
    submit.set_defaults(func=command_submit)

    init = sub.add_parser("state-init", help="创建不可覆盖的原子 JSON 状态文件")
    init.add_argument("--file", required=True)
    init.add_argument("--project-name", required=True)
    init.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    init.set_defaults(func=command_state_init)

    state_set = sub.add_parser("state-set", help="更新顶层字段或业务资源 ID")
    state_set.add_argument("--file", required=True)
    state_set.add_argument("--resource", action="store_true")
    state_set.add_argument("value")
    state_set.set_defaults(func=command_state_set)

    record = sub.add_parser("record-operation", help="记录提交结果及正确轮询地址")
    record.add_argument("--file", required=True)
    record.add_argument("--operation-id", required=True)
    record.add_argument("--operation-type", required=True)
    record.add_argument("--poll-path", required=True)
    record.add_argument("--scope", required=True)
    record.add_argument("--status", default="submitted")
    record.add_argument("--estimated-credits", default="unknown")
    record.add_argument("--json")
    record.add_argument("--json-file")
    record.set_defaults(func=command_record_operation)

    update = sub.add_parser("update-operation", help="更新已记录操作的状态")
    update.add_argument("--file", required=True)
    update.add_argument("--operation-id", required=True)
    update.add_argument("--status", required=True)
    update.add_argument("--result-url")
    update.set_defaults(func=command_update_operation)

    pending = sub.add_parser("pending", help="列出需要恢复查询的操作")
    pending.add_argument("--file", required=True)
    pending.set_defaults(func=command_pending)
    return root


def main() -> int:
    try:
        args = parser().parse_args()
        args.func(args)
    except (ClickError, json.JSONDecodeError, OSError) as exc:
        print(f"错误：{redact(str(exc))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
