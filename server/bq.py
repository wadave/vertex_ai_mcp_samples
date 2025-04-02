from typing import List, Dict, Any
from google.cloud import bigquery
from google.api_core.exceptions import NotFound
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("bigquery_server")


@mcp.tool()
def list_tables(project_id: str) -> str:
    """Lists all tables across all datasets in the specified Google Cloud project.

    Args:
        project_id: The Google Cloud project ID.
    """
    try:
        client = bigquery.Client(project=project_id)
        datasets = list(client.list_datasets())
        all_tables: List[str] = []

        if not datasets:
            return f"No datasets found in project '{project_id}'."

        for dataset in datasets:
            tables = client.list_tables(dataset.dataset_id)
            found_tables_in_dataset = False
            for table in tables:
                all_tables.append(f"{dataset.dataset_id}.{table.table_id}")
                found_tables_in_dataset = True
            # Optional: Indicate if a dataset has no tables
            # if not found_tables_in_dataset:
            #     all_tables.append(f"{dataset.dataset_id}.(no tables)")

        if not all_tables:
            return f"No tables found in any dataset within project '{project_id}'."

        return f"Tables in project '{project_id}':\n" + "\n".join(all_tables)

    except NotFound:
        return f"Error: Project '{project_id}' not found or permission denied."
    except Exception as e:
        return f"An error occurred while listing tables for project '{project_id}': {str(e)}"


@mcp.tool()
def describe_table(project_id: str, table_id_full: str) -> str:
    """Describes the schema and basic information of a specific BigQuery table.

    Args:
        project_id: The Google Cloud project ID.
        table_id_full: The full table ID in the format 'dataset_id.table_id'.
    """
    try:
        client = bigquery.Client(project=project_id)
        table = client.get_table(table_id_full)

        schema_description = [
            f"{field.name}: {field.field_type}{' (NULLABLE)' if field.is_nullable else ' (REQUIRED)'}{f' - {field.description}' if field.description else ''}"
            for field in table.schema
        ]

        description_parts = [
            f"Table: {table.full_table_id}",
            f"Description: {table.description if table.description else 'N/A'}",
            f"Created: {table.created}",
            f"Last Modified: {table.modified}",
            f"Number of Rows: {table.num_rows if table.num_rows is not None else 'N/A'}",
            f"Number of Bytes: {table.num_bytes if table.num_bytes is not None else 'N/A'}",
            "\nSchema:",
            "--------",
            "\n".join(schema_description),
        ]

        return "\n".join(description_parts)

    except NotFound:
        return f"Error: Table '{table_id_full}' not found in project '{project_id}' or permission denied."
    except ValueError as e:
        if "invalid" in str(e).lower() and "table ID" in str(e).lower():
            return f"Error: Invalid table ID format '{table_id_full}'. Please use 'dataset_id.table_id'."
        return f"An error occurred while describing table '{table_id_full}': {str(e)}"
    except Exception as e:
        return f"An error occurred while describing table '{table_id_full}': {str(e)}"


if __name__ == "__main__":
    # Example: To run this server, you might need to set up Google Cloud authentication
    # (e.g., using `gcloud auth application-default login`)
    mcp.run(transport="stdio")
