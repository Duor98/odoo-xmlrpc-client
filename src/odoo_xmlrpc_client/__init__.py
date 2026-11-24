"""Client for Odoo instances that expose the legacy XML-RPC API."""

from .client import Odoo, OdooError

__all__ = ["Odoo", "OdooError"]
