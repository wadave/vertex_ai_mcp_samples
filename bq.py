# Needed imports based on the MCP example and BigQuery requirements
from typing import Any, List, Dict
from mcp.server.fastmcp import FastMCP
# TODO: Ensure you have the google-cloud-bigquery library installed
# pip install google-cloud-bigquery
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPICallError

# Initialize FastMCP server [cite: 25]
# Using "bigquery_tool" as the server name
mcp = FastMCP("bigquery_tool")

# --- Tool Definitions ---

@mcp.tool()
def list_bq_tables(project_id: str, location: str) -> List[Dict[str, str]]:
    """
    Lists all tables across all datasets in a specified Google Cloud project and location.

    Args:
        project_id: The Google Cloud Project ID.
        location: The location of the BigQuery datasets (e.g., 'US', 'EU').

    Returns:
        A list of dictionaries, each containing 'dataset_id' and 'table_id'.
        Returns an empty list if an error occurs or no tables are found.
    """
    print(f"Attempting to list tables for project: {project_id}, location: {location}")
    tables_list = []
    try:
        # TODO: Implement BigQuery client logic here
        # 1. Initialize the BigQuery client with the project ID
        client = bigquery.Client(project=project_id) # Using project_id to access client

        # 2. List all datasets in the project
        datasets = list(client.list_datasets()) # Note: This lists datasets across all locations accessible by the client's project

        if not datasets:
             print(f"No datasets found in project {project_id}.")
             return []

        print(f"Found {len(datasets)} datasets. Checking tables...")

        # 3. Iterate through datasets and list tables for each
        for dataset in datasets:
             # Note: Dataset location check might be necessary if strict location matching is needed.
             # The client.list_tables() method requires a dataset reference.
             dataset_ref = client.dataset(dataset.dataset_id)
             bq_tables = list(client.list_tables(dataset_ref))
             print(f" Found {len(bq_tables)} tables in dataset {dataset.dataset_id}.")
             for table in bq_tables:
                 tables_list.append({
                     "dataset_id": table.dataset_id,
                     "table_id": table.table_id,
                     "full_id": f"{table.project}.{table.dataset_id}.{table.table_id}"
                 })

    except GoogleAPICallError as e:
        print(f"BigQuery API Error listing tables: {e}")
        return [{"error": f"BigQuery API Error: {e}"}]
    except Exception as e:
        print(f"An unexpected error occurred listing tables: {e}")
        # In a real scenario, provide a more user-friendly error object
        return [{"error": f"An unexpected error occurred: {e}"}]

    if not tables_list:
        print("No tables found across datasets.")
    return tables_list


@mcp.tool()
def describe_bq_table(project_id: str, location: str, dataset_id: str, table_id: str) -> Dict[str, Any]:
    """
    Describes a specific BigQuery table, returning its schema and other details.

    Args:
        project_id: The Google Cloud Project ID where the table resides.
        location: The location of the BigQuery dataset (e.g., 'US', 'EU').
        dataset_id: The ID of the dataset containing the table.
        table_id: The ID of the table to describe.

    Returns:
        A dictionary containing table details (like schema, num_rows, etc.).
        Returns a dictionary with an 'error' key if the table is not found or an error occurs.
    """
    print(f"Attempting to describe table: {project_id}.{dataset_id}.{table_id}, location: {location}")
    try:
        # TODO: Implement BigQuery client logic here
        # 1. Initialize the BigQuery client
        client = bigquery.Client(project=project_id) # Using project_id to access client

        # 2. Get the table reference
        table_ref = client.dataset(dataset_id).table(table_id)

        # 3. Fetch the table information
        table = client.get_table(table_ref)

        # 4. Format the output (schema, num_rows, etc.)
        schema_info = [{"name": field.name, "type": field.field_type, "mode": field.mode} for field in table.schema]
        description = {
            "full_id": f"{table.project}.{table.dataset_id}.{table.table_id}",
            "location": table.location, # Actual location from table info
            "num_rows": table.num_rows,
            "num_bytes": table.num_bytes,
            "created": str(table.created),
            "last_modified": str(table.modified),
            "schema": schema_info,
            "description": table.description,
            "labels": dict(table.labels) if table.labels else {}
        }
        # Note: Ensure the location matches the input if strict checking is needed. BigQuery API might return the actual location.
        # if location.upper() != table.location.upper():
        #     print(f"Warning: Table location '{table.location}' differs from requested location '{location}'.")

        return description

    except GoogleAPICallError as e:
        print(f"BigQuery API Error describing table: {e}")
        return {"error": f"BigQuery API Error: {e}"}
    except Exception as e:
        print(f"An unexpected error occurred describing table: {e}")
        return {"error": f"An unexpected error occurred: {e}"}

# Running the server (similar to the example) [cite: 32]
if __name__ == "__main__":
    # The transport 'stdio' is used for communication with the MCP host
    # (like Claude for Desktop in the example) [cite: 32]
    print("Starting BigQuery MCP server...")
    mcp.run(transport='stdio')