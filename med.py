from typing import Any
import httpx
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("medlineplus")

# Constants
MEDLINE_API_BASE = "https://wsearch.nlm.nih.gov/ws/query"
USER_AGENT = "mcp-medlineplus-tool/1.0"


@mcp.tool()
async def get_medical_term(term: str) -> str:
    """Get explanation for a medical term from MedlinePlus.

    Args:
        term: The medical term to search for.
    """
    encoded_term = quote_plus(term)
    url = f"{MEDLINE_API_BASE}?db=healthTopics&rettype=brief&term={encoded_term}"
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

            # Parse the XML response
            xml_root = ET.fromstring(response.text)

            # Find the first document's FullSummary
            # Namespace might be needed if the XML uses them, but the example doesn't show one.
            # Let's try without first.
            summary_element = xml_root.find(
                './/list/document/content[@name="FullSummary"]'
            )

            if summary_element is not None and summary_element.text:
                # The summary might contain HTML tags like <p>, return the raw text content including tags
                # We can concatenate text from child elements like <p> if needed
                summary_text = "".join(summary_element.itertext()).strip()
                if summary_text:
                    return summary_text
                else:
                    return f"Found the topic '{term}', but no summary is available."
            else:
                # Check for spelling suggestions
                spelling_suggestion = xml_root.find(".//spellingCorrection")
                if spelling_suggestion is not None and spelling_suggestion.text:
                    return f"Could not find '{term}'. Did you mean '{spelling_suggestion.text}'?"
                else:
                    return f"Could not find information for the medical term: '{term}'."

    except httpx.HTTPStatusError as e:
        return f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
    except httpx.RequestError as e:
        return f"An error occurred while requesting {e.request.url!r}: {str(e)}"
    except ET.ParseError:
        return "Error parsing XML response from MedlinePlus."
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
