from typing import List, Dict, Any
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("bigquery_tool_server")


@mcp.tool()
def list_tables(project_id: str) -> str:
    """List all tables in all datasets within a specific Google Cloud project.

    Args:
        project_id: The Google Cloud project ID where the datasets reside.
    """
    try:
        client = bigquery.Client(project=project_id)
        all_tables: List[str] = []
        datasets = list(
            client.list_datasets()
        )  # Materialize the iterator to check if empty

        if not datasets:
            return f"No datasets found in project '{project_id}'."

        for dataset in datasets:
            dataset_id = dataset.dataset_id
            try:
                tables = list(
                    client.list_tables(dataset_id)
                )  # Materialize the iterator
                if tables:
                    for table in tables:
                        all_tables.append(f"{dataset_id}.{table.table_id}")
                # Optionally: Report empty datasets if needed
                # else:
                #     all_tables.append(f"{dataset_id} (No tables)")
            except Exception as e:
                # Log the error for the specific dataset and continue
                print(
                    f"Error listing tables in dataset {dataset_id}: {e}"
                )  # Or use proper logging
                all_tables.append(f"Error accessing dataset: {dataset_id}")

        if not all_tables:
            # This case might occur if datasets exist but are all empty or inaccessible
            return f"No accessible tables found across all datasets in project '{project_id}'."

        return "Tables found:\n" + "\n".join(all_tables)

    except NotFound:
        return f"Error: Project '{project_id}' not found or you have insufficient permissions to list datasets."
    except Exception as e:
        return f"An unexpected error occurred while listing datasets or tables: {e}"


@mcp.tool()
def describe_table(project_id: str, dataset_id: str, table_id: str) -> str:
    """Describe the schema (columns and types) of a specific BigQuery table.

    Args:
        project_id: The Google Cloud project ID containing the dataset and table.
        dataset_id: The ID of the dataset containing the table.
        table_id: The ID of the table to describe.
    """
    try:
        client = bigquery.Client(project=project_id)
        table_ref = client.dataset(dataset_id).table(table_id)
        table = client.get_table(table_ref)

        schema_description: List[str] = [
            f"Schema for table {project_id}.{dataset_id}.{table_id}:"
        ]
        if not table.schema:
            schema_description.append("(No columns found in schema)")
        else:
            for field in table.schema:
                # Include name, type, mode, and description if available
                field_desc = f"- {field.name}: {field.field_type} (Mode: {field.mode})"
                if field.description:
                    field_desc += f" - Description: {field.description}"
                schema_description.append(field_desc)

        if table.description:
            schema_description.append(f"\nTable Description: {table.description}")
        else:
            schema_description.append("\n(No table description provided)")

        return "\n".join(schema_description)

    except NotFound:
        return f"Error: Table '{project_id}.{dataset_id}.{table_id}' not found or insufficient permissions."
    except Exception as e:
        return f"An unexpected error occurred while describing table '{project_id}.{dataset_id}.{table_id}': {e}"


if __name__ == "__main__":
    # Initialize and run the server using stdio transport
    mcp.run(transport="stdio")
