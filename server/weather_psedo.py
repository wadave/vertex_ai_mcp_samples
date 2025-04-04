from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"
# Helper functions
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    ...
@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)
    ...
if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
    
    
    
from mcp.server.fastmcp import FastMCP
# Initialize FastMCP server
mcp = FastMCP("Echo")

@mcp.tool()
def echo_tool(message: str) -> str:
    """Echo a message as a tool"""
    return f"Tool echo: {message}"

@mcp.resource("echo://{message}")
def echo_resource(message: str) -> str:
    """Echo a message as a resource"""
    return f"Resource echo: {message}"

@mcp.prompt()
def echo_prompt(message: str) -> str:
    """Create an echo prompt"""
    return f"Please process this message: {message}"
if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')