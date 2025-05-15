import logging
import asyncio  # Added for potential asyncio.sleep if debugging hangs

from collections.abc import AsyncIterable
from typing import Any, Literal

import httpx

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables.config import (
    RunnableConfig,
)
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)
# Basic logging config to see output during agent initialization if server fails early
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)

memory = MemorySaver()


server_configs = {
    "bnb": {
        "command": "npx",
        "args": ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
        "transport": "stdio",
    },
}


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal["input_required", "completed", "error"] = "input_required"
    message: str


class AirbnbAgent:
    """Currency Conversion Agent Example."""

    SYSTEM_INSTRUCTION = """You are a specialized assistant for airbnb accommodation.
        Your sole purpose is to use the provided tools to search for Airbnb listings and answer questions.
        You must use the tools to find information. Do not make up listings or prices.
        please include tool output, especially listing links, in your response
        Please format your response in Markdown"""

    RESPONSE_FORMAT_INSTRUCTION: str = (
        'Select status as "completed" if the request is fully addressed and no further input is needed. '
        'Select status as "input_required" if you need more information from the user or are asking a clarifying question. '
        'Select status as "error" if an error occurred or the request cannot be fulfilled.'
    )

    def __init__(self):
        logger.info("Initializing AirbnbAgent...")
        try:
            # Ensure GOOGLE_API_KEY is set in your environment.
            self.model = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-04-17")
            logger.info("ChatGoogleGenerativeAI model initialized successfully.")
        except Exception as e:
            logger.error(
                f"Failed to initialize ChatGoogleGenerativeAI model: {e}", exc_info=True
            )
            raise  # Essential to fail fast if LLM setup fails

    async def ainvoke(self, query: str, sessionId: str) -> dict[str, Any]:
        logger.info(
            f"AirbnbAgent.ainvoke (for Airbnb task) called with query: '{query}', sessionId: '{sessionId}'"
        )
        if not isinstance(sessionId, str) or not sessionId:
            logger.error(
                f"Invalid sessionId received in ainvoke: '{sessionId}'. Must be a non-empty string."
            )
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": "Internal error: Invalid session ID.",
            }
        try:
            async with MultiServerMCPClient(server_configs) as mcp_client:
                logger.debug("MultiServerMCPClient context entered for Airbnb tools.")

                tools_from_mcp = mcp_client.get_tools()
                logger.debug(f"MCP Tools for Airbnb obtained: {tools_from_mcp}")
                if not tools_from_mcp:
                    logger.warning(
                        "No MCP tools (Airbnb) were loaded. Agent might not function as expected."
                    )

                # Create a new agent instance specifically for this Airbnb invocation
                airbnb_agent_runnable = create_react_agent(
                    self.model,
                    tools=tools_from_mcp,  # Tools for Airbnb from MCP
                    checkpointer=memory,  # Shared memory checkpointer
                    prompt=self.SYSTEM_INSTRUCTION,  # Airbnb prompt
                    response_format=(self.RESPONSE_FORMAT_INSTRUCTION, ResponseFormat),
                )
                logger.debug("LangGraph React agent for Airbnb task created.")

                config: RunnableConfig = {"configurable": {"thread_id": sessionId}}
                langgraph_input = {"messages": [("user", query)]}

                logger.debug(
                    f"Invoking Airbnb agent with input: {langgraph_input} and config: {config}"
                )
                await airbnb_agent_runnable.ainvoke(
                    langgraph_input, config
                )  # Correct: pass config
                logger.debug("Airbnb agent ainvoke call completed.")

                response = self._get_agent_response_from_state(
                    config, airbnb_agent_runnable
                )
                logger.info(f"Response from Airbnb agent state: {response}")
                return response

        except httpx.HTTPStatusError as http_err:  # More specific error handling
            logger.error(
                f"HTTPStatusError in AirbnbAgent.ainvoke (Airbnb task): {http_err.response.status_code} - {http_err}",
                exc_info=True,
            )
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"An error occurred with an external service for Airbnb task: {http_err.response.status_code}",
            }
        except Exception as e:  # Catch-all for other unexpected errors
            logger.error(
                f"Unhandled exception in AirbnbAgent.ainvoke (Airbnb task): {type(e).__name__} - {e}",
                exc_info=True,
            )
            # Re-raise to let the A2A framework handle it, which should result in an error response to the client
            raise

    def _get_agent_response_from_state(
        self, config: RunnableConfig, agent_runnable
    ) -> dict[str, Any]:
        """
        Retrieves and formats the agent's response from the state of the given agent_runnable.
        """
        logger.debug(
            f"Entering _get_agent_response_from_state for config: {config} using agent: {type(agent_runnable).__name__}"
        )
        try:
            if not hasattr(agent_runnable, "get_state"):
                logger.error(
                    f"Agent runnable of type {type(agent_runnable).__name__} does not have get_state method."
                )
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": "Internal error: Agent state retrieval misconfigured.",
                }

            current_state_snapshot = agent_runnable.get_state(config)
            logger.debug(
                f"Retrieved state snapshot values: {current_state_snapshot.values if current_state_snapshot and hasattr(current_state_snapshot, 'values') else 'None or no values'}"
            )

        except Exception as e:
            logger.error(
                f"Error getting state from agent_runnable ({type(agent_runnable).__name__}): {e}",
                exc_info=True,
            )
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": "Error: Could not retrieve agent state.",
            }

        if not current_state_snapshot or not hasattr(current_state_snapshot, "values"):
            logger.error(
                f"No state snapshot or values found for config: {config} from agent {type(agent_runnable).__name__}"
            )
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": "Error: Agent state is unavailable.",
            }
        print("================")
        print("current_state_snapshot.values", current_state_snapshot.values)
        print("================")
        structured_response = current_state_snapshot.values.get("structured_response")
        if structured_response and isinstance(structured_response, ResponseFormat):
            logger.info(
                f"Formatted response from structured_response: {structured_response}"
            )
            if structured_response.status in {"input_required", "error"}:
                return {
                    "is_task_complete": False,  # Task is not complete
                    "require_user_input": structured_response.status
                    == "input_required",
                    "content": structured_response.message,
                }
            if structured_response.status == "completed":
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": structured_response.message,
                }

        # Fallback if structured_response is not as expected
        final_messages = current_state_snapshot.values.get("messages", [])
        if final_messages and isinstance(final_messages[-1], AIMessage):
            ai_content = final_messages[-1].content
            if ai_content:  # Ensure there's content
                logger.warning(
                    f"Structured response not found or not in ResponseFormat. Falling back to last AI message content for config {config}."
                )
                return {
                    "is_task_complete": True,  # Assume complete if it's a final AI message
                    "require_user_input": False,
                    "content": ai_content,
                }

        logger.warning(
            f"Structured response not found or not in expected format, and no fallback AI message. State for config {config}: {current_state_snapshot.values}"
        )
        return {
            # Default to error/input required if we can't determine status
            "is_task_complete": False,
            "require_user_input": True,
            "content": "We are unable to process your request at the moment. Please try again.",
        }

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]
