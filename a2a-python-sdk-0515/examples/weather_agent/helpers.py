from datetime import datetime
from typing import Any
from uuid import uuid4

from a2a.types import (
    Artifact,
    Message,
    Part,
    Role,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)


def update_task_with_agent_response(
    task: Task, agent_response: dict[str, Any]
) -> None:
    """Updates the provided task with the agent response."""
    task.status.timestamp = datetime.now().isoformat()
    parts: list[Part] = [Part(TextPart(text=agent_response['content']))]
    print("parts:",parts)
    if agent_response['require_user_input']:
        task.status.state = TaskState.input_required
        message = Message(
            messageId=str(uuid4()),
            role=Role.agent,
            parts=parts,
        )
        task.status.message = message
        if not task.history:
            task.history = []

        task.history.append(message)
    else:
        task.status.state = TaskState.completed
        task.status.message = None
        if not task.artifacts:
            task.artifacts = []

        artifact: Artifact = Artifact(parts=parts, artifactId=str(uuid4()))
        print("artifact:",artifact)
        task.artifacts.append(artifact)
        print("task.artifacts:",task.artifacts)




def process_streaming_agent_response(
    task: Task,
    agent_response: dict[str, Any],
) -> tuple[TaskArtifactUpdateEvent | None, TaskStatusUpdateEvent]:
    """Processes the streaming agent responses and returns TaskArtifactUpdateEvent and TaskStatusUpdateEvent."""
    is_task_complete = agent_response['is_task_complete']
    require_user_input = agent_response['require_user_input']
    parts: list[Part] = [Part(TextPart(text=agent_response['content']))]

    end_stream = False
    artifact = None
    message = None

    # responses from this agent can be working/completed/input-required
    if not is_task_complete and not require_user_input:
        task_state = TaskState.working
        message = Message(role=Role.agent, parts=parts, messageId=str(uuid4()))
    elif require_user_input:
        task_state = TaskState.input_required
        message = Message(role=Role.agent, parts=parts, messageId=str(uuid4()))
        end_stream = True
    else:
        task_state = TaskState.completed
        artifact = Artifact(parts=parts, artifactId=str(uuid4()))
        end_stream = True

    task_artifact_update_event = None

    if artifact:
        task_artifact_update_event = TaskArtifactUpdateEvent(
            taskId=task.id,
            contextId=task.contextId,
            artifact=artifact,
            append=False,
            lastChunk=True,
        )

    task_status_event = TaskStatusUpdateEvent(
        taskId=task.id,
        contextId=task.contextId,
        status=TaskStatus(
            state=task_state,
            message=message,
            timestamp=datetime.now().isoformat(),
        ),
        final=end_stream,
    )

    return task_artifact_update_event, task_status_event
