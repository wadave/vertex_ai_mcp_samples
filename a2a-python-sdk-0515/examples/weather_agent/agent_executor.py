from typing import Any, List 

import logging
from agent import WeatherAgent
from helpers import (
    process_streaming_agent_response,
    update_task_with_agent_response,
)
from typing_extensions import override

from a2a.server.agent_execution import BaseAgentExecutor
from a2a.server.events.event_queue import EventQueue
from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendStreamingMessageRequest,
    Task,
    TextPart,
    Message, 
    Role,    
)
from a2a.utils import create_task_obj
from uuid import uuid4 

logger = logging.getLogger(__name__)


class WeatherAgentExecutor(BaseAgentExecutor):
    """Weather AgentExecutor that uses an agent with preloaded tools."""

    def __init__(self, mcp_tools: List[Any]): 
        """
        Initializes the WeatherAgentExecutor.

        Args:
            mcp_tools: A list of preloaded MCP tools for the WeatherAgent.
        """
        super().__init__() # It's good practice to call super().__init__() if BaseAgentExecutor has one
        logger.info(f"Initializing WeatherAgentExecutor with {len(mcp_tools) if mcp_tools else 'no'} MCP tools.")
        self.agent = WeatherAgent(mcp_tools=mcp_tools) # Pass preloaded tools to the agent

    @override
    async def on_message_send(
        self,
        request: SendMessageRequest,
        event_queue: EventQueue,
        task: Task | None,
    ) -> None:
        """Handler for 'message/send' requests."""
        logger.info(f"on_message_send received request: {request.id}, params: {request.params.message.messageId}")
        params: MessageSendParams = request.params
        query = self._get_user_query(params)
        logger.debug(f"User query: '{query}'")

        if not task:
            logger.debug("No existing task found, creating new task.")
            task = create_task_obj(params)
        else:
            logger.debug(f"Using existing task: {task.id}")

        logger.info(f"Calling agent.ainvoke for task {task.id} with query: '{query}', contextId: {task.contextId}")
        try:
            agent_response: dict[str, Any] = await self.agent.ainvoke(
                query, task.contextId
            )
            logger.info(f"Agent.ainvoke returned for task {task.id}: {agent_response}")
            update_task_with_agent_response(task, agent_response)
            event_queue.enqueue_event(task)
            logger.info(f"Task {task.id} enqueued after agent response.")
        except Exception as e:
            logger.error(f"Error during agent.ainvoke or task update for task {task.id}: {e}", exc_info=True)
            task.status.state = "error" # Assuming TaskState.error exists or is a valid string
            error_message = f"An internal error occurred: {e}"
            if task.status.message:
                task.status.message.parts = [TextPart(text=error_message)]
            else:
                task.status.message = Message(messageId=str(uuid4()), role=Role.agent, parts=[TextPart(text=error_message)])
            event_queue.enqueue_event(task)

    @override
    async def on_message_stream(
        self,
        request: SendStreamingMessageRequest,
        event_queue: EventQueue,
        task: Task | None,
    ) -> None:
        """Handler for 'message/stream' requests."""
        logger.info(f"on_message_stream received request: {request.id}, params: {request.params.message.messageId}")
        params: MessageSendParams = request.params
        query = self._get_user_query(params)
        logger.debug(f"User query for streaming: '{query}'")

        if not task:
            logger.debug("No existing task found for streaming, creating new task.")
            task = create_task_obj(params)
            event_queue.enqueue_event(task)
            logger.info(f"Initial task {task.id} enqueued for streaming.")
        else:
            logger.debug(f"Using existing task for streaming: {task.id}")


        logger.info(f"Calling agent.stream for task {task.id} with query: '{query}', contextId: {task.contextId}")
        try:
            async for item in self.agent.stream(query, task.contextId):
                task_artifact_update_event, task_status_event = (
                    process_streaming_agent_response(task, item)
                )

                if task_artifact_update_event:
                    event_queue.enqueue_event(task_artifact_update_event)

                if task_status_event: # Ensure task_status_event is not None before enqueuing
                    event_queue.enqueue_event(task_status_event)
            logger.info(f"Streaming finished for task {task.id}.")
        except Exception as e:
            logger.error(f"Error during agent.stream for task {task.id}: {e}", exc_info=True)
            # Update task to an error state
            task.status.state = "error"
            error_message = f"An internal error occurred during streaming: {e}"
            if task.status.message:
                task.status.message.parts = [TextPart(text=error_message)]
            else:
                task.status.message = Message(messageId=str(uuid4()), role=Role.agent, parts=[TextPart(text=error_message)])
            event_queue.enqueue_event(task) # Enqueue the error state


    def _get_user_query(self, task_send_params: MessageSendParams) -> str:
        """Helper to get user query from task send params."""
        # Assuming the first part is always the text query
        if not task_send_params.message.parts:
            logger.error("No parts in message.")
            raise ValueError("Message contains no parts.")
        
        part_root = task_send_params.message.parts[0].root
        if not isinstance(part_root, TextPart):
            logger.error(f"Unsupported message part type: {type(part_root)}")
            raise ValueError('Only text parts are supported for user query.')
        return part_root.text