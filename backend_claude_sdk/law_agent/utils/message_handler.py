"""Message handling for processing agent responses."""

from typing import Any


def process_assistant_message(msg: Any, transcript: Any) -> None:
    """Process an AssistantMessage and write output to transcript file only.

    Args:
        msg: AssistantMessage to process
        transcript: TranscriptWriter instance
    """
    for block in msg.content:
        block_type = type(block).__name__

        if block_type == 'TextBlock':
            transcript.write_to_file(block.text)
