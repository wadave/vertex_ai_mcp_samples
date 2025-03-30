import asyncio
from typing import List, Dict, Any, Tuple
from google.cloud import bigquery
from google.api_core import exceptions
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("gcp_bigquery")


async def get_bq_client(project_id: str) -> bigquery.Client | None:
    """Helper to get BigQuery client, handling potential auth issues."""
    try:
        # Explicitly passing project_id ensures the client targets the correct project.
        # ADC (Application Default Credentials) should be configured in the environment where the server runs.
        client = bigquery.Client(project=project_id)
        # Test connection/permissions with a lightweight call (e.g., listing one dataset)
        # This helps catch auth/project issues early.
        list(client.list_datasets(max_results=1))
        return client
    except Exception as e:
        # Log the error server-side for debugging
        print(f"Error creating BigQuery client for project {project_id}: {e}")
        return None


async def list_tables_in_dataset(
    client: bigquery.Client, project_id: str, dataset_id: str
) -> Tuple[str, str]:
    """Helper coroutine to list tables within a single dataset."""
    tables_output = []
    try:
        tables = list(client.list_tables(dataset_id))
        if tables:
            for table in tables:
                tables_output.append(f"  - {table.table_id}")
        else:
            # Return empty string if no tables found in this dataset
            return dataset_id, "  (No tables found)"
        return dataset_id, "\n".join(tables_output)
    except exceptions.Forbidden as e:
        print(
            f"Permission denied for dataset {dataset_id} in project {project_id}: {e}"
        )
        return dataset_id, f"  - Error: Permission denied for this dataset."
    except Exception as e:
        print(f"Error listing tables in {dataset_id} for project {project_id}: {e}")
        return dataset_id, f"  - Error listing tables: {e}"


@mcp.tool()
async def list_tables_for_all_datasets(project_id: str) -> str:
    """Lists all tables within all datasets for a given Google Cloud project.

    Args:
        project_id: The Google Cloud project ID.
    """
    client = await get_bq_client(project_id)
    if not client:
        return f"Error: Could not initialize BigQuery client for project '{project_id}'. Check credentials/permissions and project existence."

    output_lines = []
    try:
        datasets = list(client.list_datasets())

        if not datasets:
            return f"No datasets found in project '{project_id}' or insufficient permissions to list them."

        output_lines.append(f"Tables in project '{project_id}':")

        # Create tasks to list tables for each dataset concurrently
        dataset_tasks = []
        for dataset in datasets:
            dataset_id = dataset.dataset_id
            dataset_tasks.append(
                asyncio.create_task(
                    list_tables_in_dataset(client, project_id, dataset_id)
                )
            )

        # Gather results from all tasks
        results = await asyncio.gather(*dataset_tasks)

        # Format results
        for dataset_id, tables_str in results:
            output_lines.append(f"\nDataset: {dataset_id}")
            output_lines.append(tables_str)

    except exceptions.Forbidden as e:
        return f"Error: Permission denied to list datasets in project '{project_id}'. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred while listing datasets/tables for project '{project_id}': {e}"

    return "\n".join(output_lines)


@mcp.tool()
async def describe_table(project_id: str, dataset_id: str, table_id: str) -> str:
    """Describes the schema (columns, types, modes) of a specific BigQuery table.

    Args:
        project_id: The Google Cloud project ID containing the table.
        dataset_id: The ID of the dataset containing the table.
        table_id: The ID of the table to describe.
    """
    client = await get_bq_client(project_id)
    if not client:
        return f"Error: Could not initialize BigQuery client for project '{project_id}'. Check credentials/permissions and project existence."

    try:
        table_ref_str = f"{project_id}.{dataset_id}.{table_id}"
        table = client.get_table(table_ref_str)  # API request

        schema_lines = [f"Schema for table '{table_ref_str}':"]
        if table.description:
            schema_lines.append(f"Table Description: {table.description}")
            schema_lines.append("Columns:")

        for field in table.schema:
            field_description = (
                f", Description: {field.description}" if field.description else ""
            )
            schema_lines.append(
                f"  - Name: {field.name}, Type: {field.field_type}, Mode: {field.mode}{field_description}"
            )

        return "\n".join(schema_lines)

    except exceptions.NotFound:
        return f"Error: Table '{project_id}.{dataset_id}.{table_id}' not found."
    except exceptions.Forbidden as e:
        return f"Error: Permission denied for table '{project_id}.{dataset_id}.{table_id}'. Details: {e}"
    except Exception as e:
        return f"An unexpected error occurred while describing table '{project_id}.{dataset_id}.{table_id}': {e}"


if __name__ == "__main__":
    # Example: Run this script directly to start the server on stdio
    print("Starting BigQuery MCP Server on stdio...")
    mcp.run(transport="stdio")
