### Openimmo Propms

OpenImmo XML importer for automated property and applicant data integration.

This app extends the [Aakvatech PropMS](https://github.com/Aakvatech-Limited/PropMS) property data model and requires both ERPNext and PropMS to be installed on the target site.

### Dependencies

- Frappe 15 or 16
- ERPNext 15 or 16
- PropMS 15.3.x or later on the v15 line

### Installation

Install the dependencies first, then install Openimmo Propms:

```bash
cd $PATH_TO_YOUR_BENCH

bench get-app erpnext --branch version-15
bench get-app https://github.com/Aakvatech-Limited/PropMS --branch version-15-hotfix
bench get-app https://github.com/Aakvatech-Limited/openimmo_propms --branch version-15-hotfix

bench --site $SITE_NAME install-app erpnext
bench --site $SITE_NAME install-app propms
bench --site $SITE_NAME install-app openimmo_propms
```

If ERPNext or PropMS is already present in the bench/site, skip the corresponding get-app/install-app commands.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/openimmo_propms
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
