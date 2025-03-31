from typing import Any
from mcp.server.fastmcp import FastMCP
from google.cloud import bigquery
from google.api_core.exceptions import NotFound, Forbidden

mcp = FastMCP(
    name="bigquery_inspector",
    version="1.0.0",
)


@mcp.tool()
def list_tables(project_id: str) -> str:
    """Lists all tables in all datasets for a given Google Cloud project.

    Args:
        project_id: The Google Cloud project ID.
    """
    try:
        client = bigquery.Client(project=project_id)
        datasets = list(client.list_datasets())
        all_tables = []
        if not datasets:
            return f"No datasets found in project {project_id}."

        for dataset in datasets:
            tables = client.list_tables(dataset.dataset_id)
            dataset_tables = [
                f"{dataset.dataset_id}.{table.table_id}" for table in tables
            ]
            if dataset_tables:
                all_tables.extend(dataset_tables)

        if not all_tables:
            return f"No tables found in any dataset for project {project_id}."

        return "\n".join(all_tables)

    except NotFound:
        return f"Error: Project or a resource within project '{project_id}' not found. Please verify the project ID and permissions."
    except Forbidden:
        return f"Error: Permission denied to access resources in project '{project_id}'. Please check your GCP credentials and IAM roles."
    except Exception as e:
        return f"An unexpected error occurred while listing tables for project '{project_id}': {e}"


@mcp.tool()
def describe_table(project_id: str, table_id: str) -> str:
    """Describes the schema of a specific BigQuery table.

    Args:
        project_id: The Google Cloud project ID.
        table_id: The full table ID in the format 'dataset_id.table_id'.
    """
    try:
        client = bigquery.Client(project=project_id)
        table = client.get_table(table_id)

        schema_description = []
        for field in table.schema:
            description = f"{field.name}: {field.field_type}"
            if field.mode:
                description += f" ({field.mode})"
            if field.description:
                description += f" - {field.description}"
            schema_description.append(description)

        return f"Schema for table {table_id}:\n" + "\n".join(schema_description)

    except NotFound:
        return f"Error: Table '{table_id}' not found in project '{project_id}'. Please verify the dataset and table name."
    except Forbidden:
        return f"Error: Permission denied to access table '{table_id}' in project '{project_id}'. Please check your GCP credentials and IAM roles."
    except ValueError as e:
        return f"Error: Invalid table ID format '{table_id}'. Expected 'dataset_id.table_id'. {e}"
    except Exception as e:
        return f"An unexpected error occurred while describing table '{table_id}' in project '{project_id}': {e}"


if __name__ == "__main__":
    # Requires google-cloud-bigquery to be installed:
    # pip install google-cloud-bigquery
    # Requires authentication, e.g., via 'gcloud auth application-default login'
    mcp.run(transport="stdio")
