from typing import Any, List, Optional
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("nih_icd")

# Constants
NIH_API_BASE = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
USER_AGENT = "mcp-nih-icd-tool/1.0"


async def make_nih_request(terms: str) -> Optional[List[Any]]:
    """Make a request to the NIH ICD-10-CM API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",  # Request JSON format
    }
    params = {
        "sf": "code,name",  # Search fields: code and name
        "terms": terms,
        "maxList": "5",  # Ask for top 5 results directly
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                NIH_API_BASE, headers=headers, params=params, timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e}")
            return None
        except Exception as e:
            print(f"An error occurred during API request: {e}")
            return None


@mcp.tool()
async def get_icd_10_code(query: str) -> str:
    """Get the top 5 ICD-10-CM codes for a given medical diagnosis name or code fragment.

    Args:
        query: The medical diagnosis name or code fragment to search for.
    """
    data = await make_nih_request(query)

    if not data:
        return "Unable to fetch ICD-10 codes from NIH API."

    # Expected format: [count, [codes], {extra_data or null}, [[code, name], ...], [code_systems or null]]
    if not isinstance(data, list) or len(data) < 4 or not isinstance(data[3], list):
        return "Received unexpected data format from NIH API."

    results = data[3]

    if not results:
        return f"No ICD-10 codes found for '{query}'."

    formatted_results = []
    for item in results:  # Already limited to 5 by API parameter
        if isinstance(item, list) and len(item) >= 2:
            code = item[0]
            name = item[1]
            formatted_results.append(f"Code: {code}, Name: {name}")
        else:
            formatted_results.append(f"Received malformed result item: {item}")

    return "\n".join(formatted_results)


if __name__ == "__main__":
    # Initialize and run the server using stdio transport
    mcp.run(transport="stdio")
