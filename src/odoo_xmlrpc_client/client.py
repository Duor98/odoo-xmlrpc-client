from __future__ import annotations

import os
import xmlrpc.client
from http.client import HTTPException
from math import isfinite
from typing import Any, Callable, Iterable, TypeVar
from urllib.parse import urlsplit
from xml.parsers.expat import ExpatError


T = TypeVar("T")


class OdooError(RuntimeError):
    """An Odoo authentication, transport, or RPC error."""


class _SingleRequest:
    def __init__(self, timeout: float) -> None:
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host: str):
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection

    def request(self, host: str, handler: str, request_body: bytes, verbose: bool = False):
        # The standard transport may retry after a disconnect, including for writes.
        return self.single_request(host, handler, request_body, verbose)


class _Transport(_SingleRequest, xmlrpc.client.Transport):
    pass


class _SafeTransport(_SingleRequest, xmlrpc.client.SafeTransport):
    pass


class Odoo:
    """Connect to an Odoo instance using a username and API key or password."""

    def __init__(
        self,
        url: str,
        db: str,
        username: str,
        password: str,
        *,
        timeout: float = 30,
    ) -> None:
        try:
            address = urlsplit(url)
            address.port  # Validate an explicitly supplied port.
        except ValueError as exc:
            raise ValueError("Invalid Odoo URL.") from exc
        if (
            address.scheme not in {"http", "https"}
            or not address.hostname
            or address.username is not None
            or address.query
            or address.fragment
        ):
            raise ValueError("Provide an HTTP(S) Odoo base URL without credentials, query, or fragment.")
        if not db or not username or not password:
            raise ValueError("An Odoo database, username, and API key or password are required.")
        if not isfinite(timeout) or timeout <= 0:
            raise ValueError("The timeout must be a positive, finite number.")

        self.db = db
        self.username = username
        self._password = password
        self.uid: int | None = None
        self._transport = _SafeTransport(timeout) if address.scheme == "https" else _Transport(timeout)
        base_url = address.geturl().rstrip("/")
        self._common = xmlrpc.client.ServerProxy(
            f"{base_url}/xmlrpc/2/common", transport=self._transport, allow_none=True
        )
        self._models = xmlrpc.client.ServerProxy(
            f"{base_url}/xmlrpc/2/object", transport=self._transport, allow_none=True
        )

    @classmethod
    def from_env(cls, *, timeout: float = 30) -> Odoo:
        """Load the connection settings from the process environment."""
        return cls(
            url=os.environ.get("ODOO_URL", ""),
            db=os.environ.get("ODOO_DB", ""),
            username=os.environ.get("ODOO_USERNAME", ""),
            password=os.environ.get("ODOO_API_KEY") or os.environ.get("ODOO_PASSWORD", ""),
            timeout=timeout,
        )

    def __enter__(self) -> Odoo:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying connection."""
        self._transport.close()

    def _call(self, operation: str, method: Callable[..., T], *args: Any) -> T:
        try:
            return method(*args)
        except xmlrpc.client.Fault as exc:
            raise OdooError(f"Odoo returned XML-RPC fault {exc.faultCode} during {operation}.") from exc
        except (xmlrpc.client.Error, OSError, HTTPException, ExpatError) as exc:
            self.close()
            raise OdooError(f"Could not complete Odoo request: {operation}.") from exc

    def version(self) -> dict[str, Any]:
        """Return server version information without authenticating."""
        return self._call("version", self._common.version)

    def authenticate(self) -> int:
        """Authenticate and return the user ID."""
        self.uid = None
        uid = self._call(
            "authentication", self._common.authenticate, self.db, self.username, self._password, {}
        )
        if type(uid) is not int or uid < 1:
            raise OdooError("Authentication failed. Check the database, username, and credentials.")
        self.uid = uid
        return uid

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        """Call an Odoo model method using the authenticated user's permissions."""
        uid = self.uid if self.uid is not None else self.authenticate()
        return self._call(
            f"{model}.{method}",
            self._models.execute_kw,
            self.db,
            uid,
            self._password,
            model,
            method,
            args or [],
            kwargs or {},
        )

    def search(self, model: str, domain: list[Any] | None = None, **kwargs: Any) -> list[int]:
        return self.execute_kw(model, "search", [domain or []], kwargs)

    def search_read(
        self,
        model: str,
        domain: list[Any] | None = None,
        fields: Iterable[str] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        if fields is not None:
            kwargs["fields"] = list(fields)
        return self.execute_kw(model, "search_read", [domain or []], kwargs)

    def search_count(self, model: str, domain: list[Any] | None = None, **kwargs: Any) -> int:
        return self.execute_kw(model, "search_count", [domain or []], kwargs)

    def read(
        self, model: str, ids: list[int], fields: Iterable[str] | None = None
    ) -> list[dict[str, Any]]:
        kwargs = {"fields": list(fields)} if fields is not None else {}
        return self.execute_kw(model, "read", [ids], kwargs)

    def create(self, model: str, values: dict[str, Any] | list[dict[str, Any]]) -> int | list[int]:
        return self.execute_kw(model, "create", [values])

    def write(self, model: str, ids: list[int], values: dict[str, Any]) -> bool:
        return self.execute_kw(model, "write", [ids, values])

    def unlink(self, model: str, ids: list[int]) -> bool:
        return self.execute_kw(model, "unlink", [ids])

    def fields_get(
        self, model: str, attributes: Iterable[str] = ("string", "type", "required")
    ) -> dict[str, Any]:
        return self.execute_kw(model, "fields_get", [], {"attributes": list(attributes)})

    def name_search(self, model: str, name: str, limit: int = 10) -> list[Any]:
        return self.execute_kw(model, "name_search", [name], {"limit": limit})
