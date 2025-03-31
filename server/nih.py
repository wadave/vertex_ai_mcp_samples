import httpx
from typing import Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("nih_icd10")

# Constants
API_BASE_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
SEARCH_FIELDS = "code,name"
MAX_RESULTS = 5


async def make_request(url: str, params: dict) -> Any:
    """Helper function to make asynchronous HTTP GET requests."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.json()
    except httpx.RequestError as exc:
        print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
        return None
    except httpx.HTTPStatusError as exc:
        print(
            f"Error response {exc.response.status_code} while requesting {exc.request.url!r}: {exc.response.text}"
        )
        return None
    except Exception as exc:
        print(f"An unexpected error occurred: {exc}")
        return None


@mcp.tool()
async def get_icd_10_code(query: str) -> str:
    """Searches the NIH ICD-10-CM database for a given code or name and returns the top 5 matching results.

    Args:
        query: The ICD-10-CM code or descriptive name to search for.
    """
    params = {"sf": SEARCH_FIELDS, "terms": query, "maxList": MAX_RESULTS}
    data = await make_request(API_BASE_URL, params)

    if not data or not isinstance(data, list) or len(data) < 4:
        return f"Could not retrieve valid data for query: {query}"

    total_results, codes, _, results_display_list = data[:4]

    if (
        not results_display_list
        or not isinstance(results_display_list, list)
        or len(results_display_list) == 0
    ):
        return f"No ICD-10-CM codes found matching '{query}'."

    formatted_results = []
    for item in results_display_list:
        if isinstance(item, list) and len(item) >= 2:
            code, name = item[:2]
            formatted_results.append(f"Code: {code}, Name: {name}")
        else:
            formatted_results.append(
                f"Skipping malformed result item: {item}"
            )  # Log or handle malformed items

    if not formatted_results:
        return f"No ICD-10-CM codes found matching '{query}'."

    return "\n".join(formatted_results)


if __name__ == "__main__":
    mcp.run(transport="stdio")
