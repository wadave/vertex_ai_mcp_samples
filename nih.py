import httpx
from typing import Any, List, Optional
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    name="nih-icd10",
    version="1.0.0",
    description="Server for searching NIH ICD-10-CM codes.",
)

# Constants
API_BASE_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
USER_AGENT = "mcp-nih-icd10-server/1.0"


async def make_api_request(query: str) -> Optional[List[Any]]:
    """Makes a request to the NIH Clinical Table Search Service API."""
    params = {"sf": "code,name", "terms": query, "count": "5"}  # Request top 5 results
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",  # Request JSON format
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                API_BASE_URL, params=params, headers=headers, timeout=30.0
            )
            response.raise_for_status()
            # The API returns JSON directly, but wrapped in a list
            data = response.json()
            if isinstance(data, list) and len(data) >= 4:
                return data  # Return the full list structure
            else:
                print(f"Unexpected API response format: {data}")
                return None
        except httpx.RequestError as e:
            print(f"HTTP Request failed: {e}")
            return None
        except httpx.HTTPStatusError as e:
            print(
                f"HTTP Status Error: {e.response.status_code} for URL: {e.request.url}"
            )
            return None
        except Exception as e:
            print(f"An unexpected error occurred during API request: {e}")
            return None


@mcp.tool()
async def get_icd_10_code(query: str) -> str:
    """Search for ICD-10-CM codes based on a name or partial code.

    Args:
        query: The search term (e.g., part of a name or code like 'tuberculos' or 'A15').

    Returns:
        A string containing the top 5 matching ICD-10-CM codes and their names, or an error message.
    """
    api_response = await make_api_request(query)

    if api_response is None:
        return "Error: Failed to fetch data from the NIH API."

    # Expected format: [total_count, [codes], null_or_extra_data, [[code1, name1], [code2, name2], ...]]
    total_results_count = api_response[0]
    results_list = api_response[3]  # This is the list of [code, name] pairs

    if not isinstance(results_list, list) or not results_list:
        return f"No ICD-10-CM codes found matching '{query}'."

    formatted_results = []
    for item in results_list:
        if isinstance(item, list) and len(item) == 2:
            code, name = item
            formatted_results.append(f"Code: {code} - Name: {name}")
        else:
            # Log unexpected item format if needed, but continue gracefully
            print(f"Skipping unexpected item format in results: {item}")

    if not formatted_results:
        return f"No valid ICD-10-CM codes found matching '{query}' after formatting."

    return (
        f"Found {total_results_count} total results. Top {len(formatted_results)} matches for '{query}':\n"
        + "\n".join(formatted_results)
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
