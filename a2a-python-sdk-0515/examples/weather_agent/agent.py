import logging
import asyncio
from collections.abc import AsyncIterable
from typing import Any, Literal, List 

import httpx

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables.config import (
    RunnableConfig,
)

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel


logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)

memory = MemorySaver()


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""
    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    message: str


class WeatherAgent:
    """Weather Agent that uses preloaded MCP tools."""

    SYSTEM_INSTRUCTION = (
        """You are a specialized assistant for weather forecast.
        Your sole purpose is to use the provided tools to search for weather and answer questions.
        You must use the tools to find information. Do not make up.
        please include tool output in your response
        Please format your response in Markdown"""
    )

    RESPONSE_FORMAT_INSTRUCTION: str = (
        'Select status as "completed" if the request is fully addressed and no further input is needed. '
        'Select status as "input_required" if you need more information from the user or are asking a clarifying question. '
        'Select status as "error" if an error occurred or the request cannot be fulfilled.'
    )

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self, mcp_tools: List[Any]): # Modified to accept mcp_tools
        """
        Initializes the WeatherAgent.

        Args:
            mcp_tools: A list of preloaded MCP (Multi-Process Controller) tools.
        """
        logger.info("Initializing WeatherAgent with preloaded MCP tools...")
        try:
            # Using the model name from your provided file
            self.model = ChatGoogleGenerativeAI(model='gemini-2.5-flash-preview-04-17')
            logger.info("ChatGoogleGenerativeAI model initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize ChatGoogleGenerativeAI model: {e}", exc_info=True)
            raise

        self.mcp_tools = mcp_tools
        if not self.mcp_tools:
            logger.warning("WeatherAgent initialized with no MCP tools. Weather search functionality may be limited.")
        else:
            logger.info(f"WeatherAgent initialized with {len(self.mcp_tools)} MCP tools.")


    async def ainvoke(self, query: str, sessionId: str) -> dict[str, Any]:
        logger.info(f"WeatherAgent.ainvoke (for Weather task) called with query: '{query}', sessionId: '{sessionId}'")
        if not isinstance(sessionId, str) or not sessionId:
            logger.error(f"Invalid sessionId received in ainvoke: '{sessionId}'. Must be a non-empty string.")
            return {
                'is_task_complete': True, 'require_user_input': False,
                'content': 'Internal error: Invalid session ID.',
            }
        try:
            # Use preloaded self.mcp_tools directly
            if not self.mcp_tools:
                logger.error("No MCP tools available for WeatherAgent.ainvoke. Cannot perform weather search.")
                return {
                    'is_task_complete': True, # Or False if you want to signal an error state differently
                    'require_user_input': False,
                    'content': "I'm sorry, but the weather tool is currently unavailable. Please try again later.",
                }
            logger.debug(f"Using preloaded MCP Tools for Weather task: {len(self.mcp_tools)} tools.")

            weather_agent_runnable = create_react_agent(
                self.model,
                tools=self.mcp_tools,  # Use preloaded tools
                checkpointer=memory,
                prompt=self.SYSTEM_INSTRUCTION,
                response_format=(self.RESPONSE_FORMAT_INSTRUCTION, ResponseFormat),
            )
            logger.debug("LangGraph React agent for Weather task created/configured with preloaded tools.")

            config: RunnableConfig = {'configurable': {'thread_id': sessionId}}
            langgraph_input = {'messages': [('user', query)]}

            logger.debug(f"Invoking Weather agent with input: {langgraph_input} and config: {config}")
            
            await weather_agent_runnable.ainvoke(langgraph_input, config)
            logger.debug("Weather agent ainvoke call completed. Fetching response from state...")

            response = self._get_agent_response_from_state(config, weather_agent_runnable)
            logger.info(f"Response from Weather agent state for session {sessionId}: {response}")
            return response

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTPStatusError in WeatherAgent.ainvoke (Weather task): {http_err.response.status_code} - {http_err}", exc_info=True)
            return {
                'is_task_complete': True, 'require_user_input': False,
                'content': f"An error occurred with an external service for Weather task: {http_err.response.status_code}",
            }
        except Exception as e:
            logger.error(f"Unhandled exception in WeatherAgent.ainvoke (Weather task): {type(e).__name__} - {e}", exc_info=True)
            # Consider whether to re-raise or return a structured error
            return {
                'is_task_complete': True, # Or False, marking task as errored
                'require_user_input': False,
                'content': f"An unexpected error occurred while processing your weather request: {type(e).__name__}.",
            }
            # Or re-raise if the executor should handle it:
            # raise

    def _get_agent_response_from_state(self, config: RunnableConfig, agent_runnable) -> dict[str, Any]:
        """
        Retrieves and formats the agent's response from the state of the given agent_runnable.
        """
        logger.debug(f"Entering _get_agent_response_from_state for config: {config} using agent: {type(agent_runnable).__name__}")
        try:
            if not hasattr(agent_runnable, 'get_state'):
                logger.error(f"Agent runnable of type {type(agent_runnable).__name__} does not have get_state method.")
                return {'is_task_complete': True, 'require_user_input': False, 'content': 'Internal error: Agent state retrieval misconfigured.'}

            current_state_snapshot = agent_runnable.get_state(config)
            # The line below caused an error in your original code because .values might not be a dict,
            # but an object from which you access attributes like .values.messages.
            # Let's be more careful accessing it.
            state_values = getattr(current_state_snapshot, 'values', None)
            logger.debug(f"Retrieved state snapshot values: {'Available' if state_values else 'Not available or None'}")


        except Exception as e:
            logger.error(f"Error getting state from agent_runnable ({type(agent_runnable).__name__}): {e}", exc_info=True)
            return {'is_task_complete': True, 'require_user_input': False, 'content': 'Error: Could not retrieve agent state.'}

        if not state_values:
            logger.error(f"No state values found for config: {config} from agent {type(agent_runnable).__name__}")
            return {'is_task_complete': True, 'require_user_input': False, 'content': 'Error: Agent state is unavailable.'}
             
        structured_response = state_values.get('structured_response') if isinstance(state_values, dict) else getattr(state_values, 'structured_response', None)

        if structured_response and isinstance(structured_response, ResponseFormat):
            logger.info(f"Formatted response from structured_response: {structured_response}")
            if structured_response.status == 'completed':
                return {
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': structured_response.message,
                }
            # For 'input_required' or 'error', the task is not complete from user's perspective
            # but might be from the agent's current turn. A2A handles task completion state.
            return {
                'is_task_complete': False, # Let A2A logic decide based on require_user_input
                'require_user_input': structured_response.status == 'input_required',
                'content': structured_response.message, # This will be the error message if status is 'error'
            }

        # Fallback if structured_response is not as expected
        final_messages = state_values.get('messages', []) if isinstance(state_values, dict) else getattr(state_values, 'messages', [])
        
        if final_messages and isinstance(final_messages[-1], AIMessage):
            ai_content = final_messages[-1].content
            if isinstance(ai_content, str) and ai_content: # Ensure it's a non-empty string
                logger.warning(f"Structured response not found or not in ResponseFormat. Falling back to last AI message content for config {config}.")
                return {
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': ai_content,
                }
            elif isinstance(ai_content, list): # Handle cases where AIMessage content might be a list of parts (e.g. text and tool calls)
                 # Try to extract text content if it's a list of parts
                text_parts = [part['text'] for part in ai_content if isinstance(part, dict) and part.get('type') == 'text']
                if text_parts:
                    logger.warning(f"Structured response not found. Falling back to concatenated text from last AI message parts for config {config}.")
                    return {
                        'is_task_complete': True,
                        'require_user_input': False,
                        'content': "\n".join(text_parts),
                    }


        logger.warning(f"Structured response not found or not in expected format, and no suitable fallback AI message. State for config {config}: {state_values}")
        return {
            'is_task_complete': False,
            'require_user_input': True, # Default to needing input or signaling an issue
            'content': 'We are unable to process your request at the moment due to an unexpected response format. Please try again.',
        }

    # stream method would also use self.mcp_tools if it similarly creates an agent instance
    async def stream(self, query: str, sessionId: str) -> AsyncIterable[Any]:
        logger.info(f"WeatherAgent.stream called with query: '{query}', sessionId: '{sessionId}'")
        if not isinstance(sessionId, str) or not sessionId:
            logger.error(f"Invalid sessionId received in stream: '{sessionId}'.")
            yield {'type': 'error', 'content': 'Internal error: Invalid session ID.'} # Example error yield
            return

        if not self.mcp_tools:
            logger.error("No MCP tools available for WeatherAgent.stream.")
            yield {'type': 'error', 'content': "Weather tool is unavailable for streaming."}
            return

        logger.debug(f"Using preloaded MCP Tools for Weather stream: {len(self.mcp_tools)} tools.")
        weather_agent_runnable = create_react_agent(
            self.model,
            tools=self.mcp_tools, # Use preloaded tools
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            # Note: ResponseFormat might not be directly applicable to intermediate streaming chunks
            # create_react_agent's stream output needs to be handled appropriately.
        )
        config: RunnableConfig = {'configurable': {'thread_id': f"stream-{sessionId}"}} # Use a different thread_id for streaming if necessary
        langgraph_input = {'messages': [('user', query)]}
        
        logger.debug(f"Streaming from Weather agent with input: {langgraph_input} and config: {config}")
        try:
            async for chunk in weather_agent_runnable.astream_events(langgraph_input, config, version="v1"): # Or astream, astream_log
                # Process and yield chunks as per your application's needs
                # The exact structure of 'chunk' depends on what create_react_agent.astream_events yields.
                # It's often a stream of events (e.g., tool calls, agent actions, final response parts).
                # You'll need to adapt this part to transform these chunks into the format expected by
                # process_streaming_agent_response.
                # For example, if it yields AIMessageChunk:
                # if chunk.get("event") == "on_chat_model_stream" and isinstance(chunk["data"]["chunk"], AIMessageChunk):
                #    yield {"type": "content", "content": chunk["data"]["chunk"].content}
                # This is a placeholder, you need to inspect the output of astream_events
                # and adapt `process_streaming_agent_response` or the yielded items.
                logger.debug(f"Stream chunk for {sessionId}: {chunk}")
                yield chunk # Yield raw chunk for now, process_streaming_agent_response will handle it
        except Exception as e:
            logger.error(f"Error during WeatherAgent.stream for session {sessionId}: {e}", exc_info=True)
            yield {'type': 'error', 'content': f"An error occurred during streaming: {type(e).__name__}"}