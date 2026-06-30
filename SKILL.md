---
name: bigquery-skill
description: Analyze data in Google BigQuery using Application Default Credentials (ADC) and answer business questions in clear, business-friendly language. Use when an assistant needs to explore BigQuery projects, datasets, tables, or schemas; map business terms such as sales, depletions, customers, brands, channels, or campaigns to warehouse tables; write efficient SQL; combine related tables with joins; export result sets to CSV; or explain BigQuery-backed findings to technical or non-technical users.
---

# BigQuery Skill

Use this skill to discover BigQuery data safely, understand schema before querying, and translate query results into concise business answers. Prefer the bundled helper script because the `bq` CLI is not installed in this environment.

## Workflow

1. Clarify the business intent
- Translate the request into likely metrics, entities, grains, and date ranges before querying.
- Map business language carefully. Treat terms such as `sales`, `depletions`, `customers`, `brands`, and `channel` as hypotheses, not facts, until the schema confirms them.
- Ask a focused clarification question before querying when a metric definition is ambiguous or when multiple tables could reasonably match the request.
- Ask for the GCP project only when it cannot be inferred from `--project`, environment variables, or ADC.

2. Explore before writing SQL
- Run `python3 scripts/bigquery_tool.py auth-check` when access is uncertain.
- List datasets, then candidate tables, then inspect schema before building joins.
- Identify join keys, date columns, partitions, clustering fields, and likely filter columns.
- Never hallucinate tables or columns. Say clearly when the needed data is not present.

3. Write efficient SQL
- Select only the required columns. Avoid `SELECT *`.
- Add date filters whenever the question implies a time range.
- Use `LIMIT` for exploration and early validation.
- Dry-run large or uncertain queries before execution.
- Match table grain before joining or aggregating. Prefer a base fact table plus the smallest required dimensions.

4. Answer for the audience
- Keep the answer concise and business-oriented unless the user asks for technical detail.
- Structure every answer like this:

### 📊 Result
- Report the key metric or answer first.
- Add one short explanation sentence.

### 📋 Breakdown
- Include a clean grouped table or top-line breakdown when helpful.
- Omit this section only when there is no meaningful grouped view.

### 🧠 Insights
- Call out trends, anomalies, comparisons, or caveats when the data supports them.
- Say briefly that there are no strong additional insights when none stand out.

### 🧾 Data Source
- Name the table or tables used.
- Explain briefly why they were chosen.

## Business Mapping Hints

- `sales` or `depletions` often live in fact tables at transaction, invoice, shipment, or aggregated distributor/customer grain.
- `customer` can mean account, outlet, retailer, distributor, or household. Confirm which one the schema actually represents.
- `brand` may map to SKU, product, brand family, portfolio, or supplier hierarchies.
- `channel` may mean on-premise, off-premise, e-commerce, retail banner, or route to market.
- `digital` or `marketing` data often requires joining campaign facts to dimension tables for brand, market, or time attributes.

## Helper Script

Use `scripts/bigquery_tool.py` for discovery and execution. It supports ADC-based auth checks, dataset and table discovery, schema inspection, dry runs, result retrieval, and CSV export.

Common commands:

```bash
python3 scripts/bigquery_tool.py auth-check
python3 scripts/bigquery_tool.py list-datasets --project my-project
python3 scripts/bigquery_tool.py list-tables --project my-project --dataset sales
python3 scripts/bigquery_tool.py schema --project my-project --dataset sales --table depletions_fact
python3 scripts/bigquery_tool.py query --project my-project --sql-file /tmp/query.sql --dry-run
python3 scripts/bigquery_tool.py query --project my-project --sql-file /tmp/query.sql --max-rows 200
python3 scripts/bigquery_tool.py query --project my-project --sql-file /tmp/query.sql --max-rows 10000 --format csv --output /tmp/bigquery-export.csv
```

## Query Rules

- Prefer exploration queries first, then production-style aggregations.
- Use dry runs before executing large or uncertain SQL.
- If the query may scan a very large amount of data, warn the user or tighten the filters before running it.
- Cap exports at roughly 10,000 rows unless the user explicitly wants a larger extract and accepts the tradeoff.
- Save SQL to a temp file for multi-line queries so it is easier to review, rerun, and dry-run.

## Notes

- The local environment has the Python BigQuery client available, but not the `bq` CLI.
- ADC is available, but a default project may not be configured. When project discovery fails, ask the user which GCP project to use.
