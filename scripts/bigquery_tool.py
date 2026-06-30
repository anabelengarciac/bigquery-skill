#!/usr/bin/env python3
"""Small helper for exploring Google BigQuery with Application Default Credentials."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import warnings
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

import google.auth
from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery

try:
    from google.cloud.bigquery.table import Row
except ImportError:  # pragma: no cover - defensive import
    Row = None

PROJECT_ENV_VARS = ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "GCP_PROJECT")
ADC_WARNING_PREFIX = (
    "Your application has authenticated using end user credentials from Google "
    "Cloud SDK without a quota project."
)


class BigQueryToolError(RuntimeError):
    """Raised when the helper cannot complete the requested operation."""


def suppress_known_warnings() -> None:
    warnings.filterwarnings(
        "ignore",
        message=f"{ADC_WARNING_PREFIX}*",
        category=UserWarning,
    )


def get_adc_context() -> tuple[Any, str | None, str | None]:
    suppress_known_warnings()
    try:
        credentials, adc_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    except DefaultCredentialsError as exc:
        raise BigQueryToolError(
            "Application Default Credentials are not configured. "
            "Run `gcloud auth application-default login` or provide valid ADC "
            "before using this helper."
        ) from exc

    env_project = next((os.getenv(name) for name in PROJECT_ENV_VARS if os.getenv(name)), None)
    return credentials, adc_project, env_project


def make_client(project: str | None, location: str | None) -> tuple[bigquery.Client, dict[str, Any]]:
    credentials, adc_project, env_project = get_adc_context()
    resolved_project = project or env_project or adc_project
    if not resolved_project:
        raise BigQueryToolError(
            "No GCP project could be determined. Pass `--project` or set "
            "`GOOGLE_CLOUD_PROJECT`."
        )

    client = bigquery.Client(
        project=resolved_project,
        credentials=credentials,
        location=location,
    )
    context = {
        "project": resolved_project,
        "project_from_adc": adc_project,
        "project_from_env": env_project,
        "location": location,
        "credential_type": type(credentials).__name__,
        "quota_project_id": getattr(credentials, "quota_project_id", None),
    }
    return client, context


def serialize_value(value: Any) -> Any:
    if Row is not None and isinstance(value, Row):
        return {key: serialize_value(item) for key, item in value.items()}
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def schema_to_dict(fields: list[bigquery.SchemaField]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for field in fields:
        output.append(
            {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": field.description,
                "fields": schema_to_dict(list(field.fields)) if field.fields else [],
            }
        )
    return output


def write_json(payload: dict[str, Any], output_path: str | None) -> None:
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(path), "format": "json"}, indent=2))
        return

    print(json.dumps(payload, indent=2, default=str))


def write_csv(rows: list[dict[str, Any]], columns: list[str], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            flat_row = {}
            for column in columns:
                value = row.get(column)
                if isinstance(value, (dict, list)):
                    flat_row[column] = json.dumps(value, ensure_ascii=False)
                else:
                    flat_row[column] = "" if value is None else str(value)
            writer.writerow(flat_row)


def load_sql(sql: str | None, sql_file: str | None) -> str:
    if bool(sql) == bool(sql_file):
        raise BigQueryToolError("Pass exactly one of `--sql` or `--sql-file`.")
    if sql_file:
        return Path(sql_file).read_text(encoding="utf-8")
    assert sql is not None
    return sql


def command_auth_check(args: argparse.Namespace) -> None:
    credentials, adc_project, env_project = get_adc_context()
    resolved_project = args.project or env_project or adc_project
    payload = {
        "adc_available": True,
        "credential_type": type(credentials).__name__,
        "quota_project_id": getattr(credentials, "quota_project_id", None),
        "project_from_adc": adc_project,
        "project_from_env": env_project,
        "resolved_project": resolved_project,
    }
    write_json(payload, args.output)


def command_list_datasets(args: argparse.Namespace) -> None:
    client, context = make_client(args.project, args.location)
    datasets = []
    for dataset in client.list_datasets(project=context["project"]):
        datasets.append(
            {
                "dataset_id": dataset.dataset_id,
                "full_dataset_id": f"{context['project']}.{dataset.dataset_id}",
                "friendly_name": dataset.friendly_name,
            }
        )

    write_json(
        {
            **context,
            "dataset_count": len(datasets),
            "datasets": datasets,
        },
        args.output,
    )


def command_list_tables(args: argparse.Namespace) -> None:
    client, context = make_client(args.project, args.location)
    dataset_ref = bigquery.DatasetReference(context["project"], args.dataset)
    tables = []
    for table in client.list_tables(dataset_ref):
        tables.append(
            {
                "table_id": table.table_id,
                "full_table_id": f"{context['project']}.{args.dataset}.{table.table_id}",
                "table_type": table.table_type,
            }
        )

    write_json(
        {
            **context,
            "dataset": args.dataset,
            "table_count": len(tables),
            "tables": tables,
        },
        args.output,
    )


def command_schema(args: argparse.Namespace) -> None:
    client, context = make_client(args.project, args.location)
    table_ref = f"{context['project']}.{args.dataset}.{args.table}"
    table = client.get_table(table_ref)

    time_partitioning = None
    if table.time_partitioning:
        time_partitioning = {
            "type": str(table.time_partitioning.type_),
            "field": table.time_partitioning.field,
            "expiration_ms": table.time_partitioning.expiration_ms,
        }

    range_partitioning = None
    if table.range_partitioning:
        range_partitioning = {
            "field": table.range_partitioning.field,
            "range": {
                "start": table.range_partitioning.range_.start,
                "end": table.range_partitioning.range_.end,
                "interval": table.range_partitioning.range_.interval,
            },
        }

    write_json(
        {
            **context,
            "table": table_ref,
            "num_rows": table.num_rows,
            "num_bytes": table.num_bytes,
            "created": serialize_value(table.created),
            "modified": serialize_value(table.modified),
            "description": table.description,
            "partitioning_type": table.partitioning_type,
            "time_partitioning": time_partitioning,
            "range_partitioning": range_partitioning,
            "clustering_fields": table.clustering_fields or [],
            "schema": schema_to_dict(list(table.schema)),
        },
        args.output,
    )


def command_query(args: argparse.Namespace) -> None:
    client, context = make_client(args.project, args.location)
    sql = load_sql(args.sql, args.sql_file)

    job_config = bigquery.QueryJobConfig(use_legacy_sql=False)
    if args.maximum_bytes_billed is not None:
        job_config.maximum_bytes_billed = args.maximum_bytes_billed

    if args.dry_run:
        # Business rule: estimate query cost before execution so ad hoc analysis stays auditable
        # and does not surprise the data owner with unnecessary warehouse spend.
        job_config.dry_run = True
        job_config.use_query_cache = False
        query_job = client.query(sql, job_config=job_config, location=args.location)
        write_json(
            {
                **context,
                "sql": sql,
                "dry_run": True,
                "estimated_bytes_processed": query_job.total_bytes_processed,
                "estimated_megabytes_processed": round(
                    query_job.total_bytes_processed / (1024 * 1024), 2
                ),
            },
            args.output,
        )
        return

    query_job = client.query(sql, job_config=job_config, location=args.location)
    result = query_job.result(max_results=args.max_rows)
    schema = query_job.schema or result.schema or []
    columns = [field.name for field in schema]
    # Business rule: keep exports row-limited by default. The assistant should prove the
    # answer path before asking for larger extracts that may contain sensitive business data.
    rows = [{column: serialize_value(row[column]) for column in columns} for row in result]
    total_rows = result.total_rows

    if args.format == "csv":
        if not args.output:
            raise BigQueryToolError("CSV export requires `--output`.")
        write_csv(rows, columns, args.output)
        payload = {
            **context,
            "sql": sql,
            "dry_run": False,
            "job_id": query_job.job_id,
            "cache_hit": query_job.cache_hit,
            "total_bytes_processed": query_job.total_bytes_processed,
            "columns": columns,
            "row_count": len(rows),
            "total_rows": total_rows,
            "truncated": total_rows is not None and total_rows > len(rows),
            "output": args.output,
            "format": "csv",
        }
        write_json(payload, None)
        return

    write_json(
        {
            **context,
            "sql": sql,
            "dry_run": False,
            "job_id": query_job.job_id,
            "cache_hit": query_job.cache_hit,
            "total_bytes_processed": query_job.total_bytes_processed,
            "columns": columns,
            "row_count": len(rows),
            "total_rows": total_rows,
            "truncated": total_rows is not None and total_rows > len(rows),
            "rows": rows,
        },
        args.output,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Explore and query BigQuery with ADC.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth_check = subparsers.add_parser(
        "auth-check",
        help="Verify ADC and resolve the active project if possible.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    auth_check.add_argument("--project", help="Optional project override.")
    auth_check.add_argument("--output", help="Optional JSON output path.")
    auth_check.set_defaults(func=command_auth_check)

    list_datasets = subparsers.add_parser(
        "list-datasets",
        help="List datasets in a project.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    list_datasets.add_argument("--project", help="Project id. Required if ADC has no default.")
    list_datasets.add_argument("--location", help="Optional BigQuery location.")
    list_datasets.add_argument("--output", help="Optional JSON output path.")
    list_datasets.set_defaults(func=command_list_datasets)

    list_tables = subparsers.add_parser(
        "list-tables",
        help="List tables in a dataset.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    list_tables.add_argument("--project", help="Project id. Required if ADC has no default.")
    list_tables.add_argument("--dataset", required=True, help="Dataset id.")
    list_tables.add_argument("--location", help="Optional BigQuery location.")
    list_tables.add_argument("--output", help="Optional JSON output path.")
    list_tables.set_defaults(func=command_list_tables)

    schema = subparsers.add_parser(
        "schema",
        help="Inspect table schema and table metadata.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    schema.add_argument("--project", help="Project id. Required if ADC has no default.")
    schema.add_argument("--dataset", required=True, help="Dataset id.")
    schema.add_argument("--table", required=True, help="Table id.")
    schema.add_argument("--location", help="Optional BigQuery location.")
    schema.add_argument("--output", help="Optional JSON output path.")
    schema.set_defaults(func=command_schema)

    query = subparsers.add_parser(
        "query",
        help="Run a query or perform a dry run.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    query.add_argument("--project", help="Project id. Required if ADC has no default.")
    query.add_argument("--sql", help="Inline SQL string.")
    query.add_argument("--sql-file", help="Path to a SQL file.")
    query.add_argument("--location", help="Optional BigQuery location.")
    query.add_argument("--dry-run", action="store_true", help="Estimate bytes without execution.")
    query.add_argument("--max-rows", type=int, default=1000, help="Maximum rows to return.")
    query.add_argument(
        "--maximum-bytes-billed",
        type=int,
        help="Abort the query if estimated billing exceeds this value.",
    )
    query.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format for executed results.",
    )
    query.add_argument("--output", help="Output file path. Required for CSV export.")
    query.set_defaults(func=command_query)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except (BigQueryToolError, GoogleAPIError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
