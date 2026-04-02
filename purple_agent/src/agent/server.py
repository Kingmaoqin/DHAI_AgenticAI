"""A2A Purple Agent Server entry point.

Starts an A2A-compatible server that can receive evaluation requests
from any green agent on the AgentBeats platform.
"""

import argparse
import logging
import sys

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from dotenv import load_dotenv

from agent.agent_logic import build_agent
from agent.executor import PurpleExecutor

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def create_app(host: str = "127.0.0.1", port: int = 9019, card_url: str | None = None):
    """Build the A2A application."""
    agent = build_agent()

    skill = AgentSkill(
        id="general_multimodal_agent",
        name=agent.name,
        description=agent.description,
        tags=["multimodal", "field_work", "document", "video", "image"],
        examples=[
            "Analyze the PPE compliance in this image.",
            "What are the start and end times of the work cycle in this video?",
            "Extract key information from this PDF document.",
        ],
    )

    url = card_url or f"http://{host}:{port}/"
    agent_card = AgentCard(
        name=agent.name,
        description=agent.description,
        url=url,
        version="0.1.0",
        default_input_modes=[
            "text",
            "text/plain",
            "application/pdf",
            "image/jpeg",
            "video/mp4",
        ],
        default_output_modes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    executor = PurpleExecutor(agent=agent)
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=handler,
    )
    return app


def main():
    parser = argparse.ArgumentParser(description="DHAI Purple Agent A2A Server")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9019)
    parser.add_argument("--card-url", type=str, default=None)
    args = parser.parse_args()

    app = create_app(host=args.host, port=args.port, card_url=args.card_url)
    logger.info("Starting DHAI Purple Agent on %s:%d", args.host, args.port)
    uvicorn.run(app.build(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
