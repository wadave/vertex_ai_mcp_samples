from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("nih_icd10")

# Constants
NIH_API_BASE = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
USER_AGENT = "mcp-nih-icd10-app/1.0"
MAX_RESULTS = 5


async def make_nih_request(url: str, params: dict[str, Any]) -> list[Any] | None:
    """Make a request to the NIH API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",  # Assuming JSON is preferred over the specific geo+json
    }
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Making request to {url} with params: {params}")
            response = await client.get(
                url, headers=headers, params=params, timeout=30.0
            )
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            logger.info(f"Received response: {response.status_code}")
            # Check if the response content type is JSON
            if "application/json" in response.headers.get("content-type", ""):
                return response.json()
            else:
                logger.error(
                    f"Unexpected content type: {response.headers.get('content-type')}"
                )
                return None
    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
        )
        return None
    except httpx.RequestError as e:
        logger.error(f"An error occurred while requesting {e.request.url!r}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None


@mcp.tool()
async def get_icd_10_code(search_term: str) -> str:
    """Get the top 5 ICD-10-CM codes based on a search term (name or code).

    Args:
        search_term: The search string (e.g., part of a word, code) for which to find matches.
    """
    params = {
        "sf": "code,name",  # Search fields: code and name
        "df": "code,name",  # Display fields: code and name
        "terms": search_term,
        "count": MAX_RESULTS,  # Limit results
    }

    data = await make_nih_request(NIH_API_BASE, params)

    if data is None:
        return "An error occurred while contacting the NIH API."

    # The API returns a list: [total_count, [codes], {extra_data}, [[code, name], ...]]
    # We need the 4th element which contains the display data.
    if not isinstance(data, list) or len(data) < 4 or not isinstance(data[3], list):
        logger.error(f"Unexpected API response format: {data}")
        return "Received an unexpected response format from the NIH API."

    results = data[3]
    total_matches = data[0]

    if not results:
        return f"No ICD-10-CM codes found matching '{search_term}'."

    formatted_results = [
        f"{i+1}. {code}: {name}" for i, (code, name) in enumerate(results)
    ]

    response_header = f"Found {total_matches} matches for '{search_term}'. Displaying top {len(results)}:\n"

    return response_header + "\n".join(formatted_results)


if __name__ == "__main__":
    logger.info("Starting NIH ICD-10 MCP Server...")
    mcp.run(transport="stdio")
