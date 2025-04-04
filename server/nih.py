from typing import Any, List
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("nih_icd")

# Constants
NIH_API_BASE = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
USER_AGENT = "mcp-nih-icd-app/1.0"
MAX_RESULTS = 5


async def make_nih_request(params: dict) -> List[Any] | None:
    """Make a request to the NIH Clinical Table Search Service API."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",  # Assuming JSON is preferred, though example shows array
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                NIH_API_BASE, headers=headers, params=params, timeout=30.0
            )
            response.raise_for_status()
            # The API returns a JSON array, not a JSON object
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e}")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None


@mcp.tool()
async def get_icd_10_code(query: str) -> str:
    """Get ICD-10-CM codes for a given diagnostic term or code fragment.

    Args:
        query: The diagnostic term or code fragment to search for (e.g., 'diabetes', 'E11').
    """
    params = {
        "sf": "code,name",
        "terms": query,
        "maxList": str(MAX_RESULTS),  # API expects string for maxList
    }

    data = await make_nih_request(params)

    if not data:
        return "Failed to retrieve data from the NIH API."

    # Response format: [total_count, [codes], {extra_data}, [[display_strings]], [code_systems]]
    # We need codes (index 1) and display_strings (index 3)
    try:
        total_count = data[0]
        if total_count == 0:
            return f"No ICD-10-CM codes found for '{query}'."

        # Ensure indices exist and have expected types
        if (
            len(data) < 4
            or not isinstance(data[1], list)
            or not isinstance(data[3], list)
        ):
            return "Received unexpected data format from the NIH API."

        codes = data[1]
        display_data = data[3]

        if not codes or not display_data or len(codes) != len(display_data):
            return "No results found or data format mismatch."

        results = []
        num_results_to_show = min(len(codes), MAX_RESULTS)

        for i in range(num_results_to_show):
            code = codes[i]
            # display_data[i] should be like ['A15.0', 'Tuberculosis of lung']
            name = (
                display_data[i][1] if len(display_data[i]) > 1 else "Name not available"
            )
            results.append(f"Code: {code}, Name: {name}")

        output = f"Found {total_count} results. Showing top {num_results_to_show}:\n"
        output += "\n".join(results)
        return output

    except (IndexError, TypeError, KeyError) as e:
        print(f"Error processing API response: {e}")
        return "Error processing the response from the NIH API."
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return "An unexpected error occurred while processing the results."


if __name__ == "__main__":
    mcp.run(transport="stdio")
