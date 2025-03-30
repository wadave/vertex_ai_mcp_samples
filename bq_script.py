from typing import List, Dict, Any
import json
from mcp.server.fastmcp import FastMCP
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

# Initialize FastMCP server
mcp = FastMCP("gcp_bigquery")


def get_bq_client(project_id: str) -> bigquery.Client:
    """Initializes and returns a BigQuery client for the specified project."""
    return bigquery.Client(project=project_id)


@mcp.tool()
def list_tables(project_id: str) -> str:
    """List all tables across all datasets in a specified Google Cloud project.

    Args:
        project_id: The Google Cloud project ID.
    """
    try:
        client = get_bq_client(project_id)
        datasets = list(client.list_datasets())
        all_tables: List[str] = []

        if not datasets:
            return f"No datasets found in project '{project_id}'."

        for dataset in datasets:
            dataset_id = dataset.dataset_id
            tables = list(client.list_tables(dataset_id))
            for table in tables:
                all_tables.append(f"{dataset_id}.{table.table_id}")

        if not all_tables:
            return f"No tables found in any dataset for project '{project_id}'."

        return "\n".join(all_tables)

    except Exception as e:
        return f"Error listing tables for project '{project_id}': {str(e)}"


@mcp.tool()
def describe_table(project_id: str, table_id_str: str) -> str:
    """Describe the schema of a specific BigQuery table.

    Args:
        project_id: The Google Cloud project ID.
        table_id_str: The full table ID in the format 'dataset_id.table_id'.
    """
    try:
        client = get_bq_client(project_id)
        table = client.get_table(table_id_str)

        schema_info: List[Dict[str, Any]] = []
        for field in table.schema:
            schema_info.append(
                {
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description,
                }
            )

        description_parts = [
            f"Table: {table.full_table_id}",
            f"Description: {table.description if table.description else 'N/A'}",
            f"Schema:",
        ]
        for field_info in schema_info:
            desc = (
                f"  - {field_info['name']} ({field_info['type']}, {field_info['mode']})"
            )
            if field_info["description"]:
                desc += f": {field_info['description']}"
            description_parts.append(desc)

        return "\n".join(description_parts)

    except NotFound:
        return f"Error: Table '{table_id_str}' not found in project '{project_id}'."
    except Exception as e:
        return f"Error describing table '{table_id_str}': {str(e)}"


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
