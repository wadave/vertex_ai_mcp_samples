from typing import Any, List, Tuple
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("nih_icd10")

# Constants
NIH_API_BASE = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
USER_AGENT = "mcp-nih-icd10-app/1.0"


async def make_nih_request(terms: str) -> List[Any] | None:
    """Make a request to the NIH Clinical Table Search Service API with error handling."""
    params = {
        "sf": "code,name",
        "terms": terms,
        "maxList": "5",  # Get top 5 results
        "df": "code,name",  # Display fields
        "cf": "code",  # Code field
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",  # Request JSON format
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                NIH_API_BASE, params=params, headers=headers, timeout=30.0
            )
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            data = response.json()
            # Basic validation of the expected list structure
            if isinstance(data, list) and len(data) >= 4:
                return data
            else:
                print(f"Unexpected API response format: {data}")
                return None
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


def format_results(data: List[Any]) -> str:
    """Format the ICD-10 results into a readable string."""
    if not data or len(data) < 4 or not isinstance(data[3], list):
        return "Could not parse results from API response."

    results_list: List[List[str]] = data[3]
    if not results_list:
        return "No matching ICD-10 codes found."

    formatted_lines = []
    for item in results_list:
        if isinstance(item, list) and len(item) == 2:
            code, name = item
            formatted_lines.append(f"Code: {code}, Name: {name}")
        else:
            # Handle unexpected item format within the results list
            formatted_lines.append(f"Skipping malformed result item: {item}")

    return "\n".join(formatted_lines)


@mcp.tool()
async def get_icd_10_code(query: str) -> str:
    """Get ICD-10-CM code information from the NIH Clinical Table Search Service.

    Searches for ICD-10-CM codes or names based on the provided query term.
    Returns the top 5 matching results.

    Args:
        query: The ICD-10-CM code or name fragment to search for.
    """
    data = await make_nih_request(query)

    if data is None:
        return "Failed to retrieve data from the NIH API."

    return format_results(data)


if __name__ == "__main__":
    # Initialize and run the server using stdio transport
    mcp.run(transport="stdio")
