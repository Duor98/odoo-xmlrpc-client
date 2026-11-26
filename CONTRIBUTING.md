# Contributing

Use Python 3.9 or later. From the repository root, create a virtual environment, install the package, and run the tests.

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

The tests start a local XML-RPC server. They run without an Odoo instance or real credentials. GitHub Actions runs the same test suite on pushes and pull requests.

For pull requests, describe the behavior you changed and include the tests you ran. For a bug report, include the Python and Odoo versions, the method called, and a minimal example with fictitious data. Remove API keys, passwords, hostnames, and customer data from examples and logs.
