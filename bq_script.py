from typing import List, Any
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bigquery_tool")


@mcp.tool()
def list_tables(project_id: str, location: str) -> str:
    """Lists all tables in all datasets within a specified Google Cloud project.

    Args:
        project_id: The Google Cloud project ID.
        location: The location of the datasets (e.g., 'US', 'EU'). Although BigQuery datasets can be regional,
                  the client often operates project-wide for listing, but location might be needed for regional resources or future features.
                  For listing datasets and tables, location is not strictly used by the client's list_datasets method but is kept for consistency.
    """
    try:
        client = bigquery.Client(project=project_id)
        datasets = list(client.list_datasets())
        result_lines = []

        if not datasets:
            return f"No datasets found in project '{project_id}'."

        result_lines.append(f"Tables in project '{project_id}' (Location: {location}):")

        for dataset in datasets:
            dataset_id = dataset.dataset_id
            result_lines.append(f"\nDataset: {dataset_id}")
            try:
                tables = list(client.list_tables(dataset_id))
                if tables:
                    for table in tables:
                        result_lines.append(f"  - {table.table_id}")
                else:
                    result_lines.append("  (No tables in this dataset)")
            except Exception as e:
                result_lines.append(
                    f"  Error listing tables for dataset {dataset_id}: {e}"
                )

        return "\n".join(result_lines)

    except NotFound:
        return f"Error: Project '{project_id}' not found or permission denied."
    except Exception as e:
        return f"An unexpected error occurred while listing tables: {e}"


@mcp.tool()
def describe_table(
    project_id: str, location: str, dataset_id: str, table_id: str
) -> str:
    """Describes the schema of a specific BigQuery table.

    Args:
        project_id: The Google Cloud project ID where the table resides.
        location: The location hint for the table (e.g., 'US', 'EU'). While table description is often global,
                  location is included for consistency and potential future regional specifics.
        dataset_id: The ID of the dataset containing the table.
        table_id: The ID of the table to describe.
    """
    try:
        client = bigquery.Client(project=project_id)
        table_ref = client.dataset(dataset_id).table(table_id)
        table = client.get_table(table_ref)

        schema_description = [
            f"Schema for table '{project_id}.{dataset_id}.{table_id}' (Location: {location}):"
        ]
        schema_description.append("Columns:")
        for field in table.schema:
            schema_description.append(
                f"  - Name: {field.name}, Type: {field.field_type}, Mode: {field.mode}"
            )

        return "\n".join(schema_description)

    except NotFound:
        return f"Error: Table '{project_id}.{dataset_id}.{table_id}' not found or permission denied."
    except Exception as e:
        return f"An unexpected error occurred while describing the table: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
