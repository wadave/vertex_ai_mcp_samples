import httpx
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("medlineplus")

# Constants
MEDLINEPLUS_API_BASE = "https://wsearch.nlm.nih.gov/ws/query"
USER_AGENT = "mcp-medlineplus-tool/1.0"


async def make_medlineplus_request(
    term: str, db: str = "healthTopics", rettype: str = "brief"
) -> Optional[ET.Element]:
    """Make a request to the MedlinePlus API and return the parsed XML root element."""
    params = {"db": db, "term": term, "rettype": rettype}
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/xml",  # Explicitly request XML
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                MEDLINEPLUS_API_BASE, params=params, headers=headers, timeout=30.0
            )
            response.raise_for_status()  # Raise an exception for bad status codes
            # Ensure content type is XML before parsing
            content_type = response.headers.get("content-type", "").lower()
            if "xml" not in content_type:
                print(f"Unexpected content type: {content_type}. Expected XML.")
                # Try parsing anyway, or handle as error
                # return None
            xml_content = response.text
            if not xml_content:
                print("Received empty response body.")
                return None
            # Parse XML content
            root = ET.fromstring(xml_content)
            return root
    except ET.ParseError as e:
        print(
            f"Error parsing XML: {e}\nContent: {xml_content[:500]}..."
        )  # Log first 500 chars
        return None
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e.response.status_code} - {e.request.url}")
        return None
    except httpx.RequestError as e:
        print(f"An error occurred while requesting {e.request.url!r}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def parse_medlineplus_response(root: ET.Element) -> Optional[str]:
    """Parse the XML root element and extract the first result's information."""
    try:
        list_element = root.find("list")
        if list_element is None:
            print("No 'list' element found in XML.")
            # Check for spelling correction
            spelling_correction = root.find("spellingCorrection")
            if spelling_correction is not None and spelling_correction.text:
                return f"Did you mean: {spelling_correction.text}?"
            return "No results found."

        first_doc = list_element.find("document")
        if first_doc is None:
            print("No 'document' element found in list.")
            return "No results found."

        content_data: Dict[str, str] = {}
        for content in first_doc.findall("content"):
            name = content.get("name")
            text = "".join(
                content.itertext()
            ).strip()  # Get all text within the element
            if name and text:
                content_data[name] = text

        title = content_data.get("title", "N/A")
        summary = content_data.get("FullSummary")  # Prioritize FullSummary
        if not summary:
            summary = content_data.get("snippet")  # Fallback to snippet

        if not summary:
            summary = "No summary or snippet available."

        # Basic cleanup of excessive whitespace potentially left by HTML tags
        summary = " ".join(summary.split())

        return f"Term: {title}\nExplanation: {summary}"

    except Exception as e:
        print(f"Error parsing document content: {e}")
        return "Error extracting information from the result."


@mcp.tool()
async def get_medical_term(medical_term: str) -> str:
    """Fetches the explanation for a given medical term from MedlinePlus.

    Args:
        medical_term: The medical term to search for.
    """
    print(f"Searching MedlinePlus for: {medical_term}")
    xml_root = await make_medlineplus_request(
        term=medical_term, rettype="brief"
    )  # Using brief first for conciseness

    if xml_root is None:
        return "Failed to retrieve information from MedlinePlus."

    result = parse_medlineplus_response(xml_root)
    if result is None:
        return "Failed to parse the response from MedlinePlus."

    print(f"Result for '{medical_term}':\n{result}")
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
