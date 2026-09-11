from __future__ import annotations

import asyncio
import unittest

from trustforge.datalease_adapters import (
    AsyncHTTPDataLeaseAdapter,
    DataLeaseBlocked,
    HTTPDataLeaseAdapter,
    MCPDataLeaseAdapter,
)


POLICY = {
    "version": "0.1",
    "purpose": "send order summary to support tool",
    "default_action": "deny",
    "hard_deny_classifiers": ["secret"],
    "destinations": {
        "http": {
            "schemes": ["https"],
            "hosts": ["support.example.com"],
            "methods": ["POST"],
        },
        "mcp": {
            "tools": ["support.create_ticket"],
        },
    },
    "rules": [
        {
            "id": "order-summary",
            "paths": ["order.id", "order.status", "items.*.sku", "items.*.quantity"],
            "action": "allow",
        },
        {
            "id": "customer-email",
            "paths": ["customer.email"],
            "classifiers": ["pii.email"],
            "action": "redact",
            "strategy": "email_domain",
        },
    ],
}

PAYLOAD = {
    "order": {"id": "A-100", "status": "shipped", "total": 39.5},
    "customer": {
        "email": "alice@example.com",
        "phone": "+1 202-555-0187",
    },
    "items": [{"sku": "SKU-1", "quantity": 2, "cost": 10.0}],
    "internal": {"api_token": "super-secret-token"},
}

EXPECTED = {
    "order": {"id": "A-100", "status": "shipped"},
    "customer": {"email": "***@example.com"},
    "items": [{"sku": "SKU-1", "quantity": 2}],
}


class DataLeaseAdapterTests(unittest.TestCase):
    def test_http_adapter_sanitizes_before_transport(self) -> None:
        calls = []

        def transport(**kwargs):
            calls.append(kwargs)
            return {"status": 201}

        adapter = HTTPDataLeaseAdapter(POLICY, transport)
        result = adapter.send_json(
            "POST",
            "https://support.example.com/tickets",
            purpose="send order summary to support tool",
            json_body=PAYLOAD,
            headers={"Authorization": "Bearer transport-secret"},
        )

        self.assertEqual(result.response, {"status": 201})
        self.assertEqual(result.destination, "support.example.com")
        self.assertEqual(calls[0]["json"], EXPECTED)
        self.assertNotIn("internal", calls[0]["json"])
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer transport-secret")

    def test_http_adapter_blocks_unauthorized_host_before_transport(self) -> None:
        calls = []

        def transport(**kwargs):
            calls.append(kwargs)
            return {"status": 200}

        adapter = HTTPDataLeaseAdapter(POLICY, transport)
        with self.assertRaises(DataLeaseBlocked) as caught:
            adapter.send_json(
                "POST",
                "https://evil.example.net/collect",
                purpose="send order summary to support tool",
                json_body=PAYLOAD,
            )

        self.assertEqual(calls, [])
        self.assertEqual(caught.exception.report["audit"][0]["rule_id"], "http-host")

    def test_http_adapter_blocks_unauthorized_method(self) -> None:
        adapter = HTTPDataLeaseAdapter(POLICY, lambda **kwargs: None)
        with self.assertRaises(DataLeaseBlocked) as caught:
            adapter.send_json(
                "DELETE",
                "https://support.example.com/tickets/1",
                purpose="send order summary to support tool",
                json_body=PAYLOAD,
            )
        self.assertEqual(caught.exception.report["audit"][0]["rule_id"], "http-method")

    def test_mcp_adapter_sanitizes_arguments_before_tool_call(self) -> None:
        calls = []

        def caller(tool_name, arguments):
            calls.append((tool_name, arguments))
            return {"ticket_id": "T-1"}

        adapter = MCPDataLeaseAdapter(POLICY, caller)
        result = adapter.call_tool(
            "support.create_ticket",
            purpose="send order summary to support tool",
            arguments=PAYLOAD,
        )

        self.assertEqual(result.response, {"ticket_id": "T-1"})
        self.assertEqual(calls, [("support.create_ticket", EXPECTED)])

    def test_mcp_adapter_blocks_unauthorized_tool(self) -> None:
        calls = []

        def caller(tool_name, arguments):
            calls.append((tool_name, arguments))
            return None

        adapter = MCPDataLeaseAdapter(POLICY, caller)
        with self.assertRaises(DataLeaseBlocked) as caught:
            adapter.call_tool(
                "analytics.upload_raw_customer",
                purpose="send order summary to support tool",
                arguments=PAYLOAD,
            )

        self.assertEqual(calls, [])
        self.assertEqual(caught.exception.report["audit"][0]["rule_id"], "mcp-tool")

    def test_authorized_destination_still_requires_authorized_purpose(self) -> None:
        calls = []
        adapter = HTTPDataLeaseAdapter(POLICY, lambda **kwargs: calls.append(kwargs))
        with self.assertRaises(DataLeaseBlocked) as caught:
            adapter.send_json(
                "POST",
                "https://support.example.com/tickets",
                purpose="send raw customer record to vendor",
                json_body=PAYLOAD,
            )

        self.assertEqual(calls, [])
        self.assertEqual(caught.exception.report["audit"][0]["rule_id"], "purpose-binding")

    def test_async_http_adapter_sanitizes_before_transport(self) -> None:
        calls = []

        async def transport(**kwargs):
            calls.append(kwargs)
            return {"status": 202}

        async def run():
            adapter = AsyncHTTPDataLeaseAdapter(POLICY, transport)
            return await adapter.send_json(
                "POST",
                "https://support.example.com/tickets",
                purpose="send order summary to support tool",
                json_body=PAYLOAD,
            )

        result = asyncio.run(run())
        self.assertEqual(result.response, {"status": 202})
        self.assertEqual(calls[0]["json"], EXPECTED)


if __name__ == "__main__":
    unittest.main()
