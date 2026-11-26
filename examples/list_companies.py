"""List the names of up to five companies using the configured Odoo instance."""

from odoo_xmlrpc_client import Odoo, OdooError


def main() -> None:
    try:
        with Odoo.from_env() as odoo:
            companies = odoo.search_read(
                "res.partner",
                [("is_company", "=", True)],
                fields=["name"],
                limit=5,
            )
    except (ValueError, OdooError) as exc:
        raise SystemExit(str(exc)) from None

    for company in companies:
        print(company["name"])


if __name__ == "__main__":
    main()
