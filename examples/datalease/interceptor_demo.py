from __future__ import annotations

import json
from pathlib import Path

from trustforge.datalease_adapters import HTTPDataLeaseAdapter, MCPDataLeaseAdapter


ROOT = Path(__file__).resolve().parent
POLICY = ROOT / "interceptor-policy.yaml"
PAYLOAD = json.loads((ROOT / "order-payload.json").read_text(encoding="utf-8"))


def main() -> None:
    http_calls = []
    mcp_calls = []

    def http_transport(**kwargs):
        http_calls.append(kwargs)
        return {"status": 201}

    def mcp_caller(tool_name, arguments):
        mcp_calls.append({"tool": tool_name, "arguments": arguments})
        return {"ticket_id": "T-100"}

    http = HTTPDataLeaseAdapter.from_policy_file(POLICY, http_transport)
    http_result = http.send_json(
        "POST",
        "https://support.example.com/tickets",
        purpose="send order summary to support tool",
        json_body=PAYLOAD,
        headers={"Authorization": "Bearer transport-owned-secret"},
    )

    mcp = MCPDataLeaseAdapter.from_policy_file(POLICY, mcp_caller)
    mcp_result = mcp.call_tool(
        "support.create_ticket",
        purpose="send order summary to support tool",
        arguments=PAYLOAD,
    )

    print(
        json.dumps(
            {
                "http": {
                    "destination": http_result.destination,
                    "sent_json": http_calls[0]["json"],
                    "summary": http_result.summary,
                },
                "mcp": {
                    "destination": mcp_result.destination,
                    "sent_arguments": mcp_calls[0]["arguments"],
                    "summary": mcp_result.summary,
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
