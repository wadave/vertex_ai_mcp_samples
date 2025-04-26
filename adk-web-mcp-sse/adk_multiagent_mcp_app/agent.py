"""
Main function to run Root Agent.
"""

import contextlib
import logging
from typing import Any, Dict, Optional, List, Tuple, Union

from dotenv import load_dotenv
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioServerParameters,
    SseServerParams,
)
from google.genai import types
import os
from pydantic import BaseModel
from .prompts import (
    ROOT_AGENT_INSTRUCTION,
    COCKTAIL_AGENT_INSTRUCTION,
    BOOKING_AGENT_INSTRUCTION,
)


class AllServerConfigs(BaseModel):
    """Define a Pydantic model for server configurations."""

    configs: Dict[str, Union[StdioServerParameters, SseServerParams]]


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


server_configs_instance = AllServerConfigs(
    configs={
        "weather": weather_sse_params,
        "bnb": bnb_server_params,
        "ct": ct_server_params,
    }
)

MODEL_ID = "gemini-2.0-flash"


async def _collect_tools_stack(
    server_config_dict: "AllServerConfigs",  # Only one argument
) -> Tuple[Dict[str, Any], contextlib.AsyncExitStack]:  # Still returns Tuple
    """Connects to servers, collects tools, and returns tools and a new stack.

    This function CREATES an AsyncExitStack to manage resources.
    The CALLER is RESPONSIBLE for properly closing the returned stack
    (e.g., using 'async with' or calling 'await stack.aclose()')
    to ensure resource cleanup (like closing server connections).

    Args:
        server_config_dict: Configuration object containing server details.

    Returns:
        A tuple containing:
            - all_tools (Dict[str, Any]): Dictionary of collected tools.
            - exit_stack (contextlib.AsyncExitStack): The newly created stack
                        containing context managers for
                        server resources. Needs cleanup
                        by the caller.
    """
    all_tools: Dict[str, Any] = {}
    # Create the master exit_stack *inside* the function
    exit_stack = contextlib.AsyncExitStack()

    # Flag to track if we successfully entered anything into the stack
    # Useful to know if stack needs closing even on partial success/early exit
    stack_needs_closing = False

    try:
        if not hasattr(server_config_dict, "configs") or not isinstance(
            server_config_dict.configs, dict
        ):
            logging.error(
                "server_config_dict does not have a valid '.configs' dictionary."
            )
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
                    logging.warning(
                        "Connection successful for key '%s', but no tools returned.",
                        key,
                    )

            except FileNotFoundError as file_error:
                logging.error(
                    "Command or script not found for key '%s': %s", key, file_error
                )
            except ConnectionRefusedError as conn_refused:
                logging.error("Connection refused for key '%s': %s", key, conn_refused)

        if not all_tools:
            logging.warning("No tools were collected from any server.")

        expected_keys = ["weather", "bnb", "ct"]
        for k in expected_keys:
            if k not in all_tools:
                logging.info(
                    "Tools for key '%s' were not collected. Ensuring key exists with empty list.",
                    k,
                )
                all_tools[k] = []

        # Return tools and the stack we created and populated
        return all_tools, exit_stack

    except Exception as e:
        # If a major error occurs during setup/loop before returning normally
        logging.error(
            "Unhandled exception in _collect_tools_one_arg: %s", e, exc_info=True
        )
        # Ensure stack is cleaned up if something was added before the error
        if stack_needs_closing:
            await exit_stack.aclose()  # Clean up immediately on function error
        # Re-raise the exception or return an indicator of failure
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
    booking_agent = LlmAgent(
        model=MODEL_ID,
        name="booking_assistant",
        instruction=BOOKING_AGENT_INSTRUCTION,
        tools=combined_booking_tools,
    )

    cocktail_agent = LlmAgent(
        model=MODEL_ID,
        name="cocktail_assistant",
        instruction=COCKTAIL_AGENT_INSTRUCTION,
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
