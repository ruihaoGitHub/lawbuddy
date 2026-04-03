"""Transcript handling for conversation history."""

import io
import logging
from datetime import datetime
from pathlib import Path


def setup_session() -> tuple[Path, Path]:
    """Setup session directory path (does not create directory).

    Returns:
        Tuple of (transcript_file_path, session_dir_path)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = Path("logs") / f"session_{timestamp}"
    transcript_file = session_dir / "transcript.txt"

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    return transcript_file, session_dir


class TranscriptWriter:
    """Helper to write output to memory buffer, save to file only on demand."""

    def __init__(self):
        self.buffer = io.StringIO()
        self.file_path: Path | None = None
        self._saved = False

    def set_save_path(self, file_path: Path):
        """Set the file path for saving."""
        self.file_path = file_path

    def write(self, text: str, end: str = "", flush: bool = True):
        """Write text to buffer."""
        print(text, end=end, flush=flush)
        self.buffer.write(text + end)

    def write_to_file(self, text: str, flush: bool = True):
        """Write text to buffer only."""
        self.buffer.write(text)

    def flush(self):
        """No-op for buffer."""
        pass

    def save_to_file(self) -> Path | None:
        """Save buffer content to file. Returns the file path if saved."""
        if self._saved or not self.file_path:
            return None

        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write(self.buffer.getvalue())
        self._saved = True
        return self.file_path

    def close(self):
        """Close the buffer."""
        self.buffer.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
        return False
