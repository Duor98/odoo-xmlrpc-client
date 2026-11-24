# Odoo XML-RPC Client

A Python client for scripts that read or update records on Odoo instances with the legacy XML-RPC API enabled. It uses Python’s standard library and requires Python 3.9 or later.

## Install

From a clone of this repository:

```sh
python -m pip install .
```

## Connect

Set these variables in the environment of your script.

| Variable | Value |
| --- | --- |
| `ODOO_URL` | Instance base URL, such as `https://odoo.example.com` |
| `ODOO_DB` | Database name |
| `ODOO_USERNAME` | Odoo login |
| `ODOO_API_KEY` | API key, preferred. Set `ODOO_PASSWORD` instead if the instance uses password authentication. |

Use HTTPS for remote instances. HTTPS connections verify certificates by default. The timeout is 30 seconds and can be set with `Odoo.from_env(timeout=10)`.

```python
from odoo_xmlrpc_client import Odoo

with Odoo.from_env() as odoo:
    partners = odoo.search_read(
        "res.partner",
        [("is_company", "=", True)],
        fields=["name"],
        limit=5,
    )
    for partner in partners:
        print(partner["name"])
```

`version()` checks the connection before authentication. The first model call authenticates automatically. For methods without a dedicated wrapper, call `execute_kw(model, method, args, kwargs)`. Use a separate client instance per thread.

Model operations use the configured Odoo user's permissions. The client sends each request once. If the connection drops during a write, check the server state before retrying it.

## Odoo compatibility

The server must expose `/xmlrpc/2/common` and `/xmlrpc/2/object`. On hosted Odoo plans, check whether your plan includes external API access. Odoo has deprecated XML-RPC and recommends JSON-2 for new integrations on servers that support it. [Odoo's external RPC documentation](https://www.odoo.com/documentation/19.0/developer/reference/external_rpc_api.html)

## Tests

```sh
python -m unittest discover -s tests -v
```

The tests use a local XML-RPC server and fictitious credentials.
