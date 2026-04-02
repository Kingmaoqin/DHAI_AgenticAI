"""A2A Purple Agent Executor.

Handles the A2A protocol lifecycle: receives requests, converts
multimodal inputs, runs the agent, and returns responses.
"""

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InvalidParamsError,
    Part,
    Task,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import new_task
from a2a.utils.errors import ServerError
from google.adk.agents import Agent, RunConfig
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import ConfigDict

from agent.multimodal import convert_parts

logger = logging.getLogger(__name__)


class _RunConfig(RunConfig):
    """Extended RunConfig that carries the task updater."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    current_task_updater: TaskUpdater


class PurpleExecutor(AgentExecutor):
    """General-purpose A2A executor that wraps a Google ADK Agent."""

    def __init__(self, agent: Agent):
        self.agent = agent
        self.runner = Runner(
            app_name=agent.name,
            agent=agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # resolve task
        if context.current_task:
            task = context.current_task
        elif context.message:
            task = new_task(context.message)
        else:
            raise ServerError(error=InvalidParamsError(message="No message provided"))

        if not context.message:
            raise ServerError(error=InvalidParamsError(message="No message provided"))

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        logger.info("Processing task %s", task.id)

        # convert A2A parts → google genai parts
        genai_parts = convert_parts(context.message.parts)
        content = types.UserContent(parts=genai_parts)

        # ensure session exists
        session = await self.runner.session_service.get_session(
            app_name=self.runner.app_name,
            user_id="self",
            session_id=task.context_id,
        )
        if session is None:
            session = await self.runner.session_service.create_session(
                app_name=self.runner.app_name,
                user_id="self",
                session_id=task.context_id,
            )

        # run agent
        response_text = ""
        async for event in self.runner.run_async(
            session_id=task.context_id,
            user_id="self",
            new_message=content,
            run_config=_RunConfig(current_task_updater=updater),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text + "\n"

            await updater.add_artifact([Part(root=TextPart(text=response_text))])
            await updater.complete()
            break

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())
