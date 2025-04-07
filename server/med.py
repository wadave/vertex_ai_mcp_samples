import httpx
import xml.etree.ElementTree as ET
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("medlineplus")

MEDLINEPLUS_API_URL = "https://wsearch.nlm.nih.gov/ws/query"


async def make_medlineplus_request(term: str) -> Optional[str]:
    """Makes a request to the MedlinePlus API and returns the XML response as a string."""
    params = {
        "db": "healthTopics",
        "term": term,
        "rettype": "brief",  # Get summary and snippets
        "retmax": 1,  # Limit to the most relevant result
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                MEDLINEPLUS_API_URL, params=params, timeout=30.0
            )
            response.raise_for_status()  # Raise an exception for bad status codes
            return response.text
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e}")
        return None
    except Exception as e:
        print(f"An error occurred during the MedlinePlus request: {e}")
        return None


def parse_summary_from_xml(xml_string: str) -> Optional[str]:
    """Parses the XML response and extracts the FullSummary content."""
    try:
        root = ET.fromstring(xml_string)
        list_element = root.find("list")
        if list_element is None:
            return None

        first_document = list_element.find("document")
        if first_document is None:
            # Check for spelling suggestions if no direct hit
            spelling_correction = root.find("spellingCorrection")
            if spelling_correction is not None and spelling_correction.text:
                return f"Did you mean: {spelling_correction.text}?"
            return None

        # Find the content element with name="FullSummary"
        for content in first_document.findall("content"):
            if content.get("name") == "FullSummary":
                # Extract text content, trying to handle potential inner tags simply
                summary_text = "".join(content.itertext()).strip()
                if summary_text:
                    return summary_text
        return None  # No summary found
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        return None
    except Exception as e:
        print(f"An error occurred during XML parsing: {e}")
        return None


@mcp.tool()
async def get_medical_term(medical_term: str) -> str:
    """Get the explanation for a specific medical term from MedlinePlus.

    Args:
        medical_term: The medical term to search for.
    """
    print(f"Searching MedlinePlus for term: {medical_term}")
    xml_response = await make_medlineplus_request(medical_term)

    if not xml_response:
        return "Failed to retrieve information from MedlinePlus."

    summary = parse_summary_from_xml(xml_response)

    if summary:
        # Check if it's a spelling suggestion
        if summary.startswith("Did you mean:"):
            return summary
        # Format the summary slightly for better readability if needed
        return f"Explanation for '{medical_term}':\n\n{summary}"
    else:
        return f"Could not find a definition or summary for '{medical_term}' on MedlinePlus."


if __name__ == "__main__":
    mcp.run(transport="stdio")
