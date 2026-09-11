from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit

from .datalease import DataLeaseError, apply_policy, load_policy


class DataLeaseBlocked(RuntimeError):
    """Raised when DataLease blocks an outbound transfer before transport execution."""

    def __init__(self, message: str, *, report: dict[str, Any], destination: str) -> None:
        super().__init__(message)
        self.report = report
        self.destination = destination


@dataclass(frozen=True)
class InterceptResult:
    """Transport response paired with value-free DataLease evidence."""

    response: Any
    destination: str
    purpose: str
    audit: list[dict[str, Any]]
    summary: dict[str, int]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise DataLeaseError("Destination bindings must be strings or lists of strings.")


def _bindings(policy: dict[str, Any], kind: str) -> dict[str, Any]:
    destinations = policy.get("destinations")
    if not isinstance(destinations, dict):
        raise DataLeaseError(
            "Interception requires a 'destinations' binding in the DataLease policy."
        )
    binding = destinations.get(kind)
    if not isinstance(binding, dict):
        raise DataLeaseError(
            f"Interception policy must declare destinations.{kind}."
        )
    return binding


def _match_any(value: str, patterns: list[str]) -> bool:
    candidate = value.casefold()
    return any(fnmatch.fnmatchcase(candidate, pattern.casefold()) for pattern in patterns)


def _authorize_http_destination(policy: dict[str, Any], method: str, url: str) -> str:
    binding = _bindings(policy, "http")
    hosts = _as_list(binding.get("hosts"))
    if not hosts:
        raise DataLeaseError("destinations.http.hosts must contain at least one host.")

    methods = [item.upper() for item in _as_list(binding.get("methods", ["POST"]))]
    schemes = [item.casefold() for item in _as_list(binding.get("schemes", ["https"]))]

    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    scheme = parsed.scheme.casefold()
    method_upper = method.upper()

    if not host or not scheme:
        raise DataLeaseBlocked(
            "Outbound HTTP request has an invalid absolute URL.",
            report=_destination_denial("http-destination", "Invalid absolute HTTP URL."),
            destination=url,
        )

    if scheme not in schemes:
        raise DataLeaseBlocked(
            f"HTTP scheme is not authorized by DataLease: {scheme}",
            report=_destination_denial("http-scheme", "HTTP scheme is not authorized."),
            destination=host,
        )

    if method_upper not in methods:
        raise DataLeaseBlocked(
            f"HTTP method is not authorized by DataLease: {method_upper}",
            report=_destination_denial("http-method", "HTTP method is not authorized."),
            destination=host,
        )

    if not _match_any(host, hosts):
        raise DataLeaseBlocked(
            f"HTTP destination is not authorized by DataLease: {host}",
            report=_destination_denial("http-host", "HTTP host is not authorized."),
            destination=host,
        )

    return host


def _authorize_mcp_destination(policy: dict[str, Any], tool_name: str) -> str:
    binding = _bindings(policy, "mcp")
    tools = _as_list(binding.get("tools"))
    if not tools:
        raise DataLeaseError("destinations.mcp.tools must contain at least one tool pattern.")

    if not _match_any(tool_name, tools):
        raise DataLeaseBlocked(
            f"MCP tool is not authorized by DataLease: {tool_name}",
            report=_destination_denial("mcp-tool", "MCP tool is not authorized."),
            destination=f"mcp:{tool_name}",
        )

    return f"mcp:{tool_name}"


def _destination_denial(rule_id: str, reason: str) -> dict[str, Any]:
    audit = [{
        "path": "$",
        "action": "deny",
        "classifiers": [],
        "rule_id": rule_id,
        "reason": reason,
    }]
    return {
        "schema_version": "0.1",
        "decision": "denied",
        "purpose": None,
        "authorized_purposes": [],
        "output": None,
        "audit": audit,
        "summary": {"allowed": 0, "redacted": 0, "denied": 1},
    }


def _project_or_block(
    policy: dict[str, Any],
    purpose: str,
    payload: Any,
    *,
    destination: str,
    block_empty: bool,
) -> dict[str, Any]:
    report = apply_policy(policy, purpose, payload)

    if report["decision"] == "denied":
        raise DataLeaseBlocked(
            "Outbound transfer denied by DataLease purpose binding.",
            report=report,
            destination=destination,
        )

    if block_empty and report.get("output") is None:
        raise DataLeaseBlocked(
            "Outbound transfer has no authorized fields after DataLease projection.",
            report=report,
            destination=destination,
        )

    return report


class HTTPDataLeaseAdapter:
    """Reference sync adapter that sanitizes a JSON body before invoking a transport."""

    def __init__(
        self,
        policy: dict[str, Any],
        transport: Callable[..., Any],
        *,
        block_empty: bool = True,
    ) -> None:
        self.policy = policy
        self.transport = transport
        self.block_empty = block_empty

    @classmethod
    def from_policy_file(
        cls,
        policy_path: str | Path,
        transport: Callable[..., Any],
        *,
        block_empty: bool = True,
    ) -> "HTTPDataLeaseAdapter":
        return cls(load_policy(policy_path), transport, block_empty=block_empty)

    def send_json(
        self,
        method: str,
        url: str,
        *,
        purpose: str,
        json_body: Any,
        headers: dict[str, str] | None = None,
        **transport_kwargs: Any,
    ) -> InterceptResult:
        destination = _authorize_http_destination(self.policy, method, url)
        report = _project_or_block(
            self.policy,
            purpose,
            json_body,
            destination=destination,
            block_empty=self.block_empty,
        )
        response = self.transport(
            method=method,
            url=url,
            json=report["output"],
            headers=headers or {},
            **transport_kwargs,
        )
        return InterceptResult(
            response=response,
            destination=destination,
            purpose=purpose,
            audit=report["audit"],
            summary=report["summary"],
        )


class AsyncHTTPDataLeaseAdapter:
    """Async counterpart of HTTPDataLeaseAdapter."""

    def __init__(
        self,
        policy: dict[str, Any],
        transport: Callable[..., Awaitable[Any]],
        *,
        block_empty: bool = True,
    ) -> None:
        self.policy = policy
        self.transport = transport
        self.block_empty = block_empty

    async def send_json(
        self,
        method: str,
        url: str,
        *,
        purpose: str,
        json_body: Any,
        headers: dict[str, str] | None = None,
        **transport_kwargs: Any,
    ) -> InterceptResult:
        destination = _authorize_http_destination(self.policy, method, url)
        report = _project_or_block(
            self.policy,
            purpose,
            json_body,
            destination=destination,
            block_empty=self.block_empty,
        )
        response = await self.transport(
            method=method,
            url=url,
            json=report["output"],
            headers=headers or {},
            **transport_kwargs,
        )
        return InterceptResult(
            response=response,
            destination=destination,
            purpose=purpose,
            audit=report["audit"],
            summary=report["summary"],
        )


class MCPDataLeaseAdapter:
    """Reference sync wrapper that sanitizes MCP tool arguments before dispatch."""

    def __init__(
        self,
        policy: dict[str, Any],
        caller: Callable[[str, Any], Any],
        *,
        block_empty: bool = True,
    ) -> None:
        self.policy = policy
        self.caller = caller
        self.block_empty = block_empty

    @classmethod
    def from_policy_file(
        cls,
        policy_path: str | Path,
        caller: Callable[[str, Any], Any],
        *,
        block_empty: bool = True,
    ) -> "MCPDataLeaseAdapter":
        return cls(load_policy(policy_path), caller, block_empty=block_empty)

    def call_tool(
        self,
        tool_name: str,
        *,
        purpose: str,
        arguments: Any,
    ) -> InterceptResult:
        destination = _authorize_mcp_destination(self.policy, tool_name)
        report = _project_or_block(
            self.policy,
            purpose,
            arguments,
            destination=destination,
            block_empty=self.block_empty,
        )
        response = self.caller(tool_name, report["output"])
        return InterceptResult(
            response=response,
            destination=destination,
            purpose=purpose,
            audit=report["audit"],
            summary=report["summary"],
        )


class AsyncMCPDataLeaseAdapter:
    """Async counterpart of MCPDataLeaseAdapter."""

    def __init__(
        self,
        policy: dict[str, Any],
        caller: Callable[[str, Any], Awaitable[Any]],
        *,
        block_empty: bool = True,
    ) -> None:
        self.policy = policy
        self.caller = caller
        self.block_empty = block_empty

    async def call_tool(
        self,
        tool_name: str,
        *,
        purpose: str,
        arguments: Any,
    ) -> InterceptResult:
        destination = _authorize_mcp_destination(self.policy, tool_name)
        report = _project_or_block(
            self.policy,
            purpose,
            arguments,
            destination=destination,
            block_empty=self.block_empty,
        )
        response = await self.caller(tool_name, report["output"])
        return InterceptResult(
            response=response,
            destination=destination,
            purpose=purpose,
            audit=report["audit"],
            summary=report["summary"],
        )
