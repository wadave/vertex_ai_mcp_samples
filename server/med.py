from typing import Any, Optional
import httpx
import xml.etree.ElementTree as ET
from mcp.server.fastmcp import FastMCP
import re

# Initialize FastMCP server
mcp = FastMCP(
    name="medlineplus",
    version="1.0.0",
    description="Provides access to MedlinePlus health information.",
)

# Constants
MEDLINEPLUS_API_BASE = "https://wsearch.nlm.nih.gov/ws/query"


# Helper function to clean HTML tags from summary
def clean_html(raw_html: Optional[str]) -> str:
    if raw_html is None:
        return "No summary available."
    # Basic cleaning: remove <p> tags and replace with newlines
    text = re.sub(r"<p>", "", raw_html)
    text = re.sub(r"</p>", "\n", text).strip()
    # Remove any other potential HTML tags (simple approach)
    text = re.sub(r"<[^>]+>", "", text)
    return text if text else "No summary available."


@mcp.tool()
async def get_medical_term(term: str) -> str:
    """Get an explanation for a medical term from MedlinePlus.

    Args:
        term: The medical term to search for.
    """
    params = {
        "db": "healthTopics",
        "term": term,
        "retmax": 1,  # Only need the top result
        "rettype": "brief",  # 'brief' includes the summary
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                MEDLINEPLUS_API_BASE, params=params, timeout=30.0
            )
            response.raise_for_status()  # Raise an exception for bad status codes

            xml_content = response.text
            root = ET.fromstring(xml_content)

            # Check if any results were found
            count = root.findtext("count")
            if count is None or int(count) == 0:
                # Check for spelling suggestions
                spelling_suggestion = root.findtext("spellingCorrection")
                if spelling_suggestion:
                    return f"No direct results found for '{term}'. Did you mean '{spelling_suggestion}'?"
                return f"No results found for the medical term: {term}"

            # Find the first document in the list
            first_doc = root.find("./list/document")
            if first_doc is None:
                return f"Could not parse the result for the medical term: {term}"

            title_element = first_doc.find("./content[@name='title']")
            summary_element = first_doc.find("./content[@name='FullSummary']")

            title = (
                title_element.text
                if title_element is not None and title_element.text
                else "N/A"
            )
            summary_raw = summary_element.text if summary_element is not None else None
            summary = clean_html(summary_raw)
            url = first_doc.get("url", "N/A")

            # Clean potential highlighting tags from title if rettype=brief was used
            cleaned_title = re.sub(r'<span class="qt\d+">(.+?)</span>', r"\1", title)

            return f"Term: {cleaned_title}\nURL: {url}\n\nExplanation:\n{summary}"

    except httpx.HTTPStatusError as e:
        return f"HTTP error occurred while fetching '{term}': {e.response.status_code} - {e.response.reason_phrase}"
    except httpx.RequestError as e:
        return f"Network error occurred while fetching '{term}': {e}"
    except ET.ParseError:
        return f"Error parsing XML response for '{term}'. The service might be unavailable or the format changed."
    except Exception as e:
        return f"An unexpected error occurred while fetching '{term}': {e}"


if __name__ == "__main__":
    # Initialize and run the server using stdio transport
    mcp.run(transport="stdio")
