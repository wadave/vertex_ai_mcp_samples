from typing import List, Dict, Any
from google.cloud import bigquery
from google.cloud.exceptions import NotFound, Forbidden
from mcp.server.fastmcp import FastMCP
import json

mcp = FastMCP(
    name="bigquery_inspector",
    version="1.0.0",
)


def get_client(project_id: str) -> bigquery.Client:
    """Initializes and returns a BigQuery client for the specified project."""
    try:
        return bigquery.Client(project=project_id)
    except Exception as e:
        # Catch potential credential or project initialization errors
        print(f"Error initializing BigQuery client for project {project_id}: {e}")
        raise ValueError(
            f"Could not initialize BigQuery client for project {project_id}. Ensure credentials are set up correctly and the project ID is valid."
        ) from e


@mcp.tool()
async def list_tables(project_id: str, location: str = "US") -> str:
    """Lists all datasets and tables within a specified Google Cloud project.

    Args:
        project_id: The Google Cloud project ID.
        location: The location of the BigQuery datasets (e.g., 'US', 'EU'). While provided, listing is typically project-wide.
    """
    try:
        client = get_client(project_id)
        datasets = list(client.list_datasets())
        if not datasets:
            return f"No datasets found in project '{project_id}'."

        output_lines = []
        for dataset in datasets:
            output_lines.append(f"Dataset: {dataset.dataset_id}")
            try:
                tables = list(client.list_tables(dataset.dataset_id))
                if tables:
                    output_lines.append("  Tables:")
                    for table in tables:
                        output_lines.append(f"    - {table.table_id}")
                else:
                    output_lines.append("  (No tables in this dataset)")
            except Forbidden as e:
                output_lines.append(
                    f"  (Permission denied for dataset {dataset.dataset_id}: {e})"
                )
            except Exception as e:
                output_lines.append(
                    f"  (Error listing tables for dataset {dataset.dataset_id}: {e})"
                )
            output_lines.append("---")

        return "\n".join(output_lines)

    except Forbidden as e:
        return f"Permission denied for project '{project_id}': {e}"
    except Exception as e:
        return f"An error occurred while listing tables for project '{project_id}': {e}"


@mcp.tool()
async def describe_table(
    project_id: str, dataset_id: str, table_id: str, location: str = "US"
) -> str:
    """Describes the schema of a specific BigQuery table.

    Args:
        project_id: The Google Cloud project ID.
        dataset_id: The ID of the dataset containing the table.
        table_id: The ID of the table to describe.
        location: The location of the BigQuery table (e.g., 'US', 'EU').
    """
    try:
        client = get_client(project_id)
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        table = client.get_table(table_ref)

        schema_description = [f"Schema for table: {table_ref}"]
        schema_description.append(f"Description: {table.description or 'N/A'}")
        schema_description.append(f"Total Rows: {table.num_rows or 'N/A'}")
        schema_description.append("Columns:")
        for field in table.schema:
            col_info = (
                f"  - Name: {field.name}, Type: {field.field_type}, Mode: {field.mode}"
            )
            if field.description:
                col_info += f", Description: {field.description}"
            schema_description.append(col_info)
            # Handle nested fields if necessary (basic example here)
            if field.field_type == "RECORD" or field.field_type == "STRUCT":
                for sub_field in field.fields:
                    sub_col_info = f"    - Nested Name: {sub_field.name}, Type: {sub_field.field_type}, Mode: {sub_field.mode}"
                    if sub_field.description:
                        sub_col_info += f", Description: {sub_field.description}"
                    schema_description.append(sub_col_info)

        return "\n".join(schema_description)

    except NotFound:
        return f"Error: Table '{table_ref}' not found in project '{project_id}'."
    except Forbidden as e:
        return f"Permission denied for table '{table_ref}': {e}"
    except Exception as e:
        return f"An error occurred while describing table '{table_ref}': {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
