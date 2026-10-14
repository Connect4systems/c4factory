### C4Factory

Factory App

### Item units of measure

Use the Item's **Default Unit of Measure** for stock quantities and its existing
**Units of Measure** table for item-specific conversions. Create each UOM (such as
Kilogram) once and reuse it across items. A conversion factor is the number of
default units in one additional unit:

| Item | Default UOM | Additional UOM | Conversion Factor |
| --- | --- | --- | --- |
| Pins 3 cm | Piece | Kilogram | 300 |
| Pins 5 cm | Piece | Kilogram | 200 |

Receiving 2 Kilograms therefore adds 600 Pieces of Pins 3 cm or 400 Pieces of
Pins 5 cm. No global Kilogram-to-Piece conversion is needed. Purchase and Sales
UOMs must also be listed in the item's table when they differ from its default.
Factors must be positive, UOM rows unique, and the default UOM factor must be 1.
ERPNext transactions retain their own conversion factors and stock quantities;
editing an item factor does not rewrite submitted transactions.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app c4factory
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/c4factory
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
