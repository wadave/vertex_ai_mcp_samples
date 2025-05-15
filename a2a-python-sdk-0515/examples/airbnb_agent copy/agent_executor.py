from typing import Any

import logging  # Add logging
from agent import AirbnbAgent
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
)
from a2a.utils import create_task_obj

logger = logging.getLogger(__name__)  # Add logger


class AirbnbAgentExecutor(BaseAgentExecutor):
    """Currency AgentExecutor Example."""

    def __init__(self):
        self.agent = AirbnbAgent()

    @override
    async def on_message_send(
        self,
        request: SendMessageRequest,
        event_queue: EventQueue,
        task: Task | None,
    ) -> None:
        """Handler for 'message/send' requests."""
        logger.info(
            f"on_message_send received request: {request.id}, params: {request.params.message.messageId}"
        )
        params: MessageSendParams = request.params
        query = self._get_user_query(params)
        logger.debug(f"User query: '{query}'")

        if not task:
            logger.debug("No existing task found, creating new task.")
            task = create_task_obj(params)
        else:
            logger.debug(f"Using existing task: {task.id}")

        # invoke the underlying agent
        logger.info(
            f"Calling agent.ainvoke for task {task.id} with query: '{query}', contextId: {task.contextId}"
        )
        try:
            agent_response: dict[str, Any] = await self.agent.ainvoke(
                query, task.contextId
            )
            logger.info(f"Agent.ainvoke returned for task {task.id}: {agent_response}")
            update_task_with_agent_response(task, agent_response)
            event_queue.enqueue_event(task)
            logger.info(f"Task {task.id} enqueued after agent response.")
        except Exception as e:
            logger.error(
                f"Error during agent.ainvoke or task update for task {task.id}: {e}",
                exc_info=True,
            )
            # Optionally, update task to an error state and enqueue
            task.status.state = "error"  # Assuming TaskState.error exists
            if task.status.message:
                task.status.message.parts = [
                    TextPart(text=f"An internal error occurred: {e}")
                ]
            else:  # Create a new message if none exists
                from uuid import uuid4
                from a2a.types import Message, Role  # Local import for brevity

                task.status.message = Message(
                    messageId=str(uuid4()),
                    role=Role.agent,
                    parts=[TextPart(text=f"An internal error occurred: {e}")],
                )
            event_queue.enqueue_event(task)  # Enqueue the error state

    @override
    async def on_message_stream(
        self,
        request: SendStreamingMessageRequest,
        event_queue: EventQueue,
        task: Task | None,
    ) -> None:
        """Handler for 'message/stream' requests."""
        logger.info(
            f"on_message_stream received request: {request.id}, params: {request.params.message.messageId}"
        )
        params: MessageSendParams = request.params
        query = self._get_user_query(params)
        logger.debug(f"User query for streaming: '{query}'")

        if not task:
            logger.debug("No existing task found for streaming, creating new task.")
            task = create_task_obj(params)
            # emit the initial task so it is persisted to TaskStore
            event_queue.enqueue_event(task)
            logger.info(f"Initial task {task.id} enqueued for streaming.")

        # kickoff the streaming agent and process responses
        async for item in self.agent.stream(
            query, task.contextId
        ):  # Ensure agent.stream is async generator
            task_artifact_update_event, task_status_event = (
                process_streaming_agent_response(task, item)
            )

            if task_artifact_update_event:
                event_queue.enqueue_event(task_artifact_update_event)

            event_queue.enqueue_event(task_status_event)
        logger.info(f"Streaming finished for task {task.id}.")

    def _get_user_query(self, task_send_params: MessageSendParams) -> str:
        """Helper to get user query from task send params."""
        part = task_send_params.message.parts[0].root
        if not isinstance(part, TextPart):
            raise ValueError("Only text parts are supported")
        return part.text
