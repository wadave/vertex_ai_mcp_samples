import os
from typing import List, Dict, Any
from mcp.server.fastmcp import FastMCP
from google.cloud import bigquery
from google.api_core.exceptions import NotFound, Forbidden

# Initialize FastMCP server
mcp = FastMCP("gcp_bigquery")


# --- Helper Functions ---
def get_bigquery_client(project_id: str) -> bigquery.Client:
    """Initializes and returns a BigQuery client for the given project ID."""
    # TODO: Add more robust authentication handling if needed
    # For local development, ensure 'gcloud auth application-default login' has been run.
    # For deployments, ensure appropriate service account credentials are available.
    return bigquery.Client(project=project_id)


# --- MCP Tools ---
@mcp.tool()
def list_tables(project_id: str, location: str) -> str:
    """Lists all tables across all datasets in a specified Google Cloud project.

    Args:
        project_id: The Google Cloud project ID.
        location: The location (e.g., 'US', 'EU') although BigQuery datasets/tables are often global or multi-regional within a project context, location might be relevant for client routing or filtering in some scenarios. Currently primarily used for client context.

    Returns:
        A string listing all tables in the format 'dataset_id.table_id', or an error message.
    """
    try:
        client = get_bigquery_client(project_id)
        datasets = list(client.list_datasets())
        all_tables: List[str] = []

        if not datasets:
            return f"No datasets found in project '{project_id}'."

        for dataset in datasets:
            try:
                tables = list(client.list_tables(dataset.dataset_id))
                for table in tables:
                    all_tables.append(f"{dataset.dataset_id}.{table.table_id}")
            except (NotFound, Forbidden) as e:
                # Log this but continue if possible, maybe only one dataset has issues
                print(
                    f"Warning: Could not list tables for dataset '{dataset.dataset_id}': {e}"
                )
                all_tables.append(
                    f"Error listing tables in {dataset.dataset_id}: Access Denied or Not Found"
                )
            except Exception as e:
                print(
                    f"Warning: An unexpected error occurred listing tables for dataset '{dataset.dataset_id}': {e}"
                )
                all_tables.append(
                    f"Error listing tables in {dataset.dataset_id}: {type(e).__name__}"
                )

        if not all_tables:
            return f"No tables found in any dataset for project '{project_id}'."

        return "\n".join(all_tables)

    except Forbidden:
        return f"Error: Permission denied to list resources in project '{project_id}'. Check GCP IAM permissions."
    except NotFound:
        return f"Error: Project '{project_id}' not found or no access."
    except Exception as e:
        print(f"Error listing tables for project '{project_id}': {e}")
        return f"An unexpected error occurred: {type(e).__name__}"


@mcp.tool()
def describe_table(
    project_id: str, location: str, dataset_id: str, table_id: str
) -> str:
    """Describes the schema of a specific BigQuery table.

    Args:
        project_id: The Google Cloud project ID.
        location: The location context. Not directly used for table fetch but kept for consistency.
        dataset_id: The ID of the dataset containing the table.
        table_id: The ID of the table to describe.

    Returns:
        A string describing the table's schema (column name and type), or an error message.
    """
    try:
        client = get_bigquery_client(project_id)
        table_ref = client.dataset(dataset_id).table(table_id)
        table = client.get_table(table_ref)

        schema_description: List[str] = [
            f"Schema for table: {project_id}.{dataset_id}.{table_id}"
        ]
        if table.description:
            schema_description.append(f"Description: {table.description}")
        schema_description.append("Columns:")
        for field in table.schema:
            schema_description.append(
                f"  - {field.name}: {field.field_type} ({'NULLABLE' if field.is_nullable else 'REQUIRED'}) {'[REPEATED]' if field.mode == 'REPEATED' else ''}"
            )
            if field.description:
                schema_description.append(f"    Description: {field.description}")

        return "\n".join(schema_description)

    except NotFound:
        return f"Error: Table '{project_id}.{dataset_id}.{table_id}' not found."
    except Forbidden:
        return f"Error: Permission denied to describe table '{project_id}.{dataset_id}.{table_id}'. Check GCP IAM permissions."
    except Exception as e:
        print(f"Error describing table '{project_id}.{dataset_id}.{table_id}': {e}")
        return f"An unexpected error occurred: {type(e).__name__}"


# --- Main Execution ---
if __name__ == "__main__":
    # Requires google-cloud-bigquery to be installed:
    # pip install google-cloud-bigquery
    # Ensure authentication is set up (e.g., gcloud auth application-default login)
    mcp.run(transport="stdio")
