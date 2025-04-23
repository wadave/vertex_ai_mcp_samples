"""
Main function to run Root Agent.
"""

import asyncio
import contextlib
import json
import logging
from typing import Any, Dict, Optional, List, Tuple

from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from google.genai import types
from pydantic import BaseModel


class AllServerConfigs(BaseModel):
    """Define a Pydantic model for server configurations."""

    configs: Dict[str, StdioServerParameters]


load_dotenv()


session_service = InMemorySessionService()
artifacts_service = InMemoryArtifactService()

# Create server parameters for stdio connection
weather_server_params = StdioServerParameters(
    command="python",
    args=["adk_multiagent_mcp_app/mcp_server/weather_server.py"],
)

ct_server_params = StdioServerParameters(
    command="python",
    args=["adk_multiagent_mcp_app/mcp_server/cocktail.py"],
)

bnb_server_params = StdioServerParameters(
    command="npx", args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]
)

server_configs_instance = AllServerConfigs(
    configs={
        "weather": weather_server_params,
        "bnb": bnb_server_params,
        "ct": ct_server_params,
    }
)

MODEL_ID = "gemini-2.0-flash"

ROOT_AGENT_INSTRUCTION = """
**Role:** You are a Virtual Assistant acting as a Request Router. You can help user with questions regarding cocktails, weather, and booking accommodations.

**Primary Goal:** Analyze user requests and route them to the correct specialist sub-agent.

**Capabilities & Routing:**
* **Greetings:** If the user greets you, respond warmly and directly.
* **Cocktails:** Route requests about cocktails, drinks, recipes, or ingredients to `cocktail_assistant`.
* **Booking & Weather:** Route requests about booking accommodations (any type) or checking weather to `booking_assistant`.
* **Out-of-Scope:** If the request is unrelated (e.g., general knowledge, math), state directly that you cannot assist with that topic.

**Key Directives:**
* **Delegate Immediately:** Once a suitable sub-agent is identified, route the request without asking permission.
* **Do Not Answer Delegated Topics:** You must **not** attempt to answer questions related to cocktails, booking, or weather yourself. Always delegate.
* **Formatting:** Format your final response to the user using Markdown for readability.
"""


async def _collect_tools_stack(
    server_config_dict: 'AllServerConfigs', # Only one argument
) -> Tuple[Dict[str, Any], contextlib.AsyncExitStack]: # Still returns Tuple
    """Connects to servers, collects tools, and returns tools and a new stack.

    This function CREATES an AsyncExitStack to manage resources.
    The CALLER is RESPONSIBLE for properly closing the returned stack
    (e.g., using 'async with' or calling 'await stack.aclose()')
    to ensure resource cleanup (like closing server connections).

    Assumes MCPToolset.from_server exists and returns (tools, exit_stack).

    Args:
        server_config_dict: Configuration object containing server details.

    Returns:
        A tuple containing:
            - all_tools (Dict[str, Any]): Dictionary of collected tools.
            - master_stack (contextlib.AsyncExitStack): The newly created stack
                        containing context managers for
                        server resources. Needs cleanup
                        by the caller.
    """
    all_tools: Dict[str, Any] = {}
    # Create the master stack *inside* the function
    exit_stack = contextlib.AsyncExitStack()

    # Flag to track if we successfully entered anything into the stack
    # Useful to know if stack needs closing even on partial success/early exit
    stack_needs_closing = False

    try:
        if not hasattr(server_config_dict, "configs") or not isinstance(
            server_config_dict.configs, dict
        ):
            logging.error("server_config_dict does not have a valid '.configs' dictionary.")
            # Return empty tools and the newly created (empty) stack
            # Caller still needs to handle this stack, even if empty.
            return {}, exit_stack

        for key, server_params in server_config_dict.configs.items():
            individual_exit_stack: Optional[contextlib.AsyncExitStack] = None
            try:
                tools, individual_exit_stack = await MCPToolset.from_server(
                    connection_params=server_params
                )

                if individual_exit_stack:
                    # Enter the individual stack into the master stack
                    await exit_stack.enter_async_context(individual_exit_stack)
                    stack_needs_closing = True  # Mark that we added something

                if tools:
                    all_tools[key] = tools
                else:
                    logging.warning("Connection successful for key '%s', but no tools returned.", key)

            except FileNotFoundError as file_error:
                logging.error("Command or script not found for key '%s': %s", key, file_error)
            except ConnectionRefusedError as conn_refused:
                logging.error("Connection refused for key '%s': %s", key, conn_refused)

        if not all_tools:
            logging.warning(
                "No tools were collected from any server."
            )

        expected_keys = ["weather", "bnb", "ct"]
        for k in expected_keys:
            if k not in all_tools:
                logging.info(
                    "Tools for key '%s' were not collected. Ensuring key exists with empty list.", k
                )
                all_tools[k] = []

        # Return tools and the stack we created and populated
        return all_tools, exit_stack

    except Exception as e:
        # If a major error occurs during setup/loop before returning normally
        logging.error("Unhandled exception in _collect_tools_one_arg: %s", e, exc_info=True)
        # Ensure stack is cleaned up if something was added before the error
        if stack_needs_closing:
            await exit_stack.aclose()  # Clean up immediately on function error
        # Re-raise the exception or return an indicator of failure
        # Returning the stack might be misleading if we closed it here.
        # Option: return ({}, None) or raise - depends on desired error handling
        raise  # Re-raising is often cleaner


async def create_agent():
    """Gets tools from MCP Server."""
    all_tools, exit_stack = await _collect_tools_stack(server_configs_instance)

    # Prepare tool lists, defensively accessing keys
    booking_tools = all_tools.get("bnb", [])
    weather_tools = all_tools.get("weather", [])
    # Create a new list to avoid modifying the original list in all_tools if needed elsewhere
    combined_booking_tools = list(booking_tools)
    combined_booking_tools.extend(weather_tools)

    ct_tools = all_tools.get("ct", [])

    # --- Agent Creation ---
    # *** Assumes LlmAgent is defined and imported ***
    booking_agent = LlmAgent(
        model=MODEL_ID,
        name="booking_assistant",
        instruction="""Use booking_tools to handle inquiries related to
        booking accommodations (rooms, condos, houses, apartments, town-houses),
        and checking weather information.
        Format your response using Markdown.
        If you don't know how to help, or none of your tools are appropriate for it,
        call the function "agent_exit" hand over the task to other sub agent.""",
        tools=combined_booking_tools,
    )

    cocktail_agent = LlmAgent(
        model=MODEL_ID,
        name="cocktail_assistant",
        instruction="""Use ct_tools to handle all inquiries related to cocktails,
        drink recipes, ingredients,and mixology.
        Format your response using Markdown.
        If you don't know how to help, or none of your tools are appropriate for it,
        call the function "agent_exit" hand over the task to other sub agent.""",
        tools=ct_tools,
    )

    agent = LlmAgent(
        model=MODEL_ID,
        name="ai_assistant",
        instruction=ROOT_AGENT_INSTRUCTION,
        sub_agents=[cocktail_agent, booking_agent],
    )
    return agent, exit_stack

root_agent = create_agent()

