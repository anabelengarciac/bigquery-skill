# BigQuery Skill

![Status](https://img.shields.io/badge/status-showcase_ready-2ea44f)
![Domain](https://img.shields.io/badge/domain-analytics_engineering-0969da)
![Stack](https://img.shields.io/badge/stack-python_%7C_bigquery_%7C_adc-6f42c1)

An AI-assisted BigQuery workflow that turns vague business questions into reproducible, cost-aware SQL exploration. It is designed for analytics environments where the hardest part is rarely writing SQL, but deciding which tables, grains, filters, and metric definitions are safe to trust.

## Why It Matters

This skill demonstrates how I structure data work when accuracy, cost control, and business readability all matter. It guides an agent through schema discovery, dry runs, efficient querying, CSV exports, and executive-style answers without hallucinating tables or columns.

| Business value | Technical value |
| --- | --- |
| Faster answers to ad hoc data questions | BigQuery client wrapper with auth checks and dry runs |
| Reduced risk of wrong joins or misunderstood metrics | Explicit schema-first workflow and grain validation |
| Clear outputs for non-technical stakeholders | Standard answer format with result, breakdown, insights, and data source |
| Safer exploration of large warehouses | Query limits, selective columns, and export controls |

## What It Can Do

- Discover projects, datasets, tables, schemas, and row samples.
- Validate Application Default Credentials before running analysis.
- Dry-run SQL before execution to reduce cost surprises.
- Export query results to JSON or CSV for downstream analysis.
- Translate business terms such as sales, customers, brands, campaigns, and channels into schema hypotheses before querying.
- Return concise business-facing answers with traceable source tables.

## Workflow

```mermaid
flowchart LR
    A["Business question"] --> B["Clarify metric, grain, date range"]
    B --> C["Discover datasets and schemas"]
    C --> D["Validate joins and filters"]
    D --> E["Dry-run SQL"]
    E --> F["Execute or export"]
    F --> G["Business answer with caveats"]
```

## Repository Structure

```text
.
|-- SKILL.md                  # Codex skill instructions
|-- agents/openai.yaml        # Agent metadata
`-- scripts/bigquery_tool.py  # BigQuery discovery/query CLI
```

## Example Commands

```bash
python3 scripts/bigquery_tool.py auth-check
python3 scripts/bigquery_tool.py list-datasets --project my-project
python3 scripts/bigquery_tool.py schema --project my-project --dataset sales --table orders
python3 scripts/bigquery_tool.py query --project my-project --sql-file /tmp/query.sql --dry-run
python3 scripts/bigquery_tool.py query --project my-project --sql-file /tmp/query.sql --format csv --output /tmp/export.csv
```

## Design Principles

- Explore before answering.
- Treat business language as a hypothesis until schema confirms it.
- Prefer narrow, auditable SQL over broad extracts.
- Make cost and data-source caveats explicit.
- Present findings in language a business audience can act on.

## Skills Demonstrated

`BigQuery`  -  `Python CLI design`  -  `analytics engineering`  -  `data discovery`  -  `SQL quality control`  -  `business translation`  -  `AI workflow design`

## Security

This is a sanitized showcase repository. It contains no credentials, service-account files, warehouse names, or private datasets. Authentication is expected through local Application Default Credentials.
