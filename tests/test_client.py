from __future__ import annotations

import os
import threading
import unittest
from unittest.mock import patch
from xmlrpc.client import Fault, loads
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from odoo_xmlrpc_client import Odoo, OdooError


class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/xmlrpc/2/common", "/xmlrpc/2/object")

    def do_POST(self) -> None:
        if not self.server.drop_next_request:
            super().do_POST()
            return
        self.server.drop_next_request = False
        payload = self.rfile.read(int(self.headers["Content-Length"]))
        args, method = loads(payload)
        self.server.funcs[method](*args)
        self.close_connection = True


class ClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calls = []
        self.server = SimpleXMLRPCServer(
            ("127.0.0.1", 0), requestHandler=RequestHandler, logRequests=False
        )
        self.server.drop_next_request = False
        self.addCleanup(self.server.server_close)
        self.server.register_function(lambda: {"server_version": "18.0"}, "version")
        self.server.register_function(self.authenticate, "authenticate")
        self.server.register_function(self.execute_kw, "execute_kw")
        thread = threading.Thread(target=self.server.serve_forever, args=(0.01,), daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = Odoo(self.url, "test_db", "demo@example.com", "test-key")
        self.addCleanup(self.client.close)

    def authenticate(self, db, username, password, context):
        self.calls.append(("authenticate", db, username, password, context))
        if (db, username, password) == ("test_db", "demo@example.com", "test-key"):
            return 7
        return False

    def execute_kw(self, db, uid, password, model, method, args, kwargs):
        self.calls.append((method, db, uid, password, model, args, kwargs))
        if method == "search_read":
            return [{"name": "Example Company"}]
        if method == "search_count":
            return 1
        if method == "create":
            return 42
        raise Fault(1, "Unknown method")

    def test_version_does_not_authenticate(self) -> None:
        self.assertEqual(self.client.version(), {"server_version": "18.0"})
        self.assertEqual(self.calls, [])

    def test_environment_and_authenticated_model_calls(self) -> None:
        settings = {
            "ODOO_URL": self.url,
            "ODOO_DB": "test_db",
            "ODOO_USERNAME": "demo@example.com",
            "ODOO_API_KEY": "test-key",
            "ODOO_PASSWORD": "unused-password",
        }
        with patch.dict(os.environ, settings, clear=True), Odoo.from_env() as odoo:
            domain = [("is_company", "=", True)]
            self.assertEqual(
                odoo.search_read("res.partner", domain, fields=["name"], limit=5),
                [{"name": "Example Company"}],
            )
            self.assertEqual(odoo.search_count("res.partner"), 1)
        self.assertEqual([call[0] for call in self.calls], ["authenticate", "search_read", "search_count"])
        self.assertEqual(
            self.calls[1],
            ("search_read", "test_db", 7, "test-key", "res.partner",
             [[["is_company", "=", True]]], {"fields": ["name"], "limit": 5}),
        )

    def test_rejected_authentication_stops_model_call(self) -> None:
        with Odoo(self.url, "test_db", "demo@example.com", "wrong-key") as odoo:
            with self.assertRaisesRegex(OdooError, "Authentication failed"):
                odoo.search_count("res.partner")
            self.assertIsNone(odoo.uid)
        self.assertEqual([call[0] for call in self.calls], ["authenticate"])

    def test_rpc_fault_reports_model_and_method(self) -> None:
        with self.assertRaisesRegex(OdooError, r"fault 1 during res.partner.unknown"):
            self.client.execute_kw("res.partner", "unknown")

    def test_lost_response_does_not_repeat_create(self) -> None:
        self.client.authenticate()
        self.server.drop_next_request = True
        with self.assertRaisesRegex(OdooError, r"res.partner.create"):
            self.client.create("res.partner", {"name": "Example Company"})
        self.assertEqual([call[0] for call in self.calls], ["authenticate", "create"])
        self.assertEqual(self.client.search_count("res.partner"), 1)

    def test_connection_rejects_credentials_embedded_in_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "without credentials"):
            Odoo("https://demo:secret@odoo.example.com", "test_db", "demo", "test-key")
