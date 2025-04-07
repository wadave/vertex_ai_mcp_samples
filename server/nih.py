from typing import Any, List, Tuple
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    "nih_icd10cm",
    version="1.0.0",
    description="Server to search for ICD-10-CM codes using the NIH Clinical Table Search Service.",
)

# Constants
NIH_API_BASE = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
USER_AGENT = "mcp-nih-icd10cm-tool/1.0"


async def make_nih_request(term: str) -> List[Any] | None:
    """Make a request to the NIH Clinical Table Search Service API."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",  # Ensure we get JSON
    }
    params = {
        "sf": "code,name",  # Search fields: code and name
        "terms": term,
        "count": "5",  # Get top 5 results
        "df": "code,name",  # Display fields: code and name
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                NIH_API_BASE, headers=headers, params=params, timeout=30.0
            )
            response.raise_for_status()  # Raise exception for 4xx or 5xx status codes
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e}")
            return None
        except httpx.RequestError as e:
            print(f"Request error occurred: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None


@mcp.tool()
async def get_icd_10_code(term: str) -> str:
    """Search for ICD-10-CM codes by name or code using the NIH Clinical Table Search Service.

    Args:
        term: The search term (e.g., part of a code or name like 'diabetes' or 'E11').
    """
    print(f"Searching for ICD-10-CM term: {term}")
    data = await make_nih_request(term)

    if data is None:
        return "Error: Failed to fetch data from the NIH API."

    # Expected response format: [totalCount, [codes], {extraData}, [[displayFields]], [codeSystems]]
    # We need the 4th element (index 3)
    if not isinstance(data, list) or len(data) < 4 or not isinstance(data[3], list):
        print(f"Unexpected API response format: {data}")
        return "Error: Received unexpected data format from the NIH API."

    results: List[List[str]] = data[3]

    if not results:
        return f"No ICD-10-CM codes found matching '{term}'."

    formatted_results = []
    for result_pair in results:
        if len(result_pair) == 2:
            code, name = result_pair
            formatted_results.append(f"Code: {code} - Name: {name}")
        else:
            print(f"Skipping malformed result item: {result_pair}")

    if not formatted_results:
        return (
            f"No valid ICD-10-CM code/name pairs found matching '{term}' after parsing."
        )

    return "\n".join(formatted_results)


if __name__ == "__main__":
    mcp.run(transport="stdio")
