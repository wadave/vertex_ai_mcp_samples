"""
Main function to run Root Agent.
"""

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
    SseServerParams,
)
import os
from .prompts import (
    ROOT_AGENT_INSTRUCTION,
    COCKTAIL_AGENT_INSTRUCTION,
    BOOKING_AGENT_INSTRUCTION,
)


load_dotenv()

service_name = os.getenv("SERVICE_NAME")
project_number = os.getenv("PROJECT_NUMBER")
region = os.getenv("GOOGLE_CLOUD_LOCATION", 'us-central1')

sse_url = f"https://{service_name}-{project_number}.{region}.run.app/sse"

weather_sse_params = SseServerParams(
    url=sse_url
)

ct_server_params = StdioServerParameters(
    command="python",
    args=["adk_multiagent_mcp_app/stdio_server/cocktail.py"],
)

bnb_server_params = StdioServerParameters(
    command="npx", args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]
)


MODEL_ID = "gemini-2.0-flash"


# --- Agent Creation ---
def create_agent() -> LlmAgent:
    """
    Creates the root LlmAgent and its sub-agents using pre-loaded MCP tools.

    Args:
        loaded_mcp_tools: A dictionary of tools, typically populated at application
                        startup, where keys are toolset identifiers (e.g., "bnb",
                        "weather", "ct") and values are the corresponding tools.

    Returns:
        An LlmAgent instance representing the root agent, configured with sub-agents.
    """
    booking_agent = LlmAgent(
        model=MODEL_ID,
        name="booking_assistant",
        instruction=BOOKING_AGENT_INSTRUCTION,
        tools=[
            MCPToolset(connection_params=bnb_server_params),
            MCPToolset(connection_params=weather_sse_params),
        ],
    )

    cocktail_agent = LlmAgent(
        model=MODEL_ID,
        name="cocktail_assistant",
        instruction=COCKTAIL_AGENT_INSTRUCTION,
        tools=[MCPToolset(connection_params=ct_server_params)],
    )

    root_agent = LlmAgent(
        model=MODEL_ID,
        name="ai_assistant",
        instruction=ROOT_AGENT_INSTRUCTION,
        sub_agents=[cocktail_agent, booking_agent],
    )
    return root_agent


root_agent = create_agent()
