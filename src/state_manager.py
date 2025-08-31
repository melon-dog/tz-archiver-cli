"""
State management for persistent storage of processed CIDs and errors.
Handles loading and saving of application state to disk.
"""

import json
from pathlib import Path
from typing import Set, Optional
from dataclasses import dataclass

from config import Config
from utils.logger import Logger


logger = Logger("StateManager")


@dataclass
class SpiderState:
    """Spider mode state container."""

    current_position: Optional[int] = None
    start_position: Optional[int] = None
    step_size: Optional[int] = None
    total_token_space: Optional[int] = None
    tokens_visited: int = 0
    seed_data: Optional[str] = None  # To ensure consistent initialization


@dataclass
class AppState:
    """Application state container."""

    processed_cids: Set[str]
    error_cids: Set[str]
    spider_state: Optional[SpiderState] = None

    def __post_init__(self):
        """Ensure sets are properly initialized."""
        if not isinstance(self.processed_cids, set):
            self.processed_cids = (
                set(self.processed_cids) if self.processed_cids else set()
            )
        if not isinstance(self.error_cids, set):
            self.error_cids = set(self.error_cids) if self.error_cids else set()
        if self.spider_state is None:
            self.spider_state = SpiderState()


class StateManager:
    """Manages persistent state storage and retrieval."""

    def __init__(self):
        self.processed_file = Config.PROCESSED_CIDS_FILE
        self.errors_file = Config.ERRORS_CIDS_FILE
        self.spider_file = Config.DATA_DIR / "spider_state.json"

    def _load_cids_from_file(self, file_path: Path) -> Set[str]:
        """Load CIDs from a JSON file."""
        if not file_path.exists():
            return set()

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
            logger.error(f"Failed to load {file_path.name}: {e}")
            return set()

    def _save_cids_to_file(self, cids: Set[str], file_path: Path) -> bool:
        """Save CIDs to a JSON file."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(sorted(list(cids)), f, indent=2, ensure_ascii=False)
            return True
        except (IOError, TypeError) as e:
            logger.error(f"Failed to save {file_path.name}: {e}")
            return False

    def _load_spider_state(self) -> SpiderState:
        """Load spider state from file."""
        if not self.spider_file.exists():
            return SpiderState()

        try:
            with open(self.spider_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return SpiderState(
                    current_position=data.get("current_position"),
                    start_position=data.get("start_position"),
                    step_size=data.get("step_size"),
                    total_token_space=data.get("total_token_space"),
                    tokens_visited=data.get("tokens_visited", 0),
                    seed_data=data.get("seed_data"),
                )
        except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
            logger.error(f"Failed to load spider state: {e}")
            return SpiderState()

    def _save_spider_state(self, spider_state: SpiderState) -> bool:
        """Save spider state to file."""
        try:
            # Ensure data directory exists
            self.spider_file.parent.mkdir(exist_ok=True)

            data = {
                "current_position": spider_state.current_position,
                "start_position": spider_state.start_position,
                "step_size": spider_state.step_size,
                "total_token_space": spider_state.total_token_space,
                "tokens_visited": spider_state.tokens_visited,
                "seed_data": spider_state.seed_data,
            }

            with open(self.spider_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except (IOError, TypeError) as e:
            logger.error(f"Failed to save spider state: {e}")
            return False

    def load_state(self) -> AppState:
        """Load application state from disk."""
        processed_cids = self._load_cids_from_file(self.processed_file)
        error_cids = self._load_cids_from_file(self.errors_file)
        spider_state = self._load_spider_state()

        logger.info(f"Loaded {len(processed_cids)} processed CIDs")
        logger.info(f"Loaded {len(error_cids)} error CIDs")

        if spider_state.current_position is not None:
            logger.info(
                f"Loaded spider state - Position: {spider_state.current_position:,}, Visited: {spider_state.tokens_visited:,}"
            )
        else:
            logger.info("No previous spider state found - will start fresh")

        return AppState(
            processed_cids=processed_cids,
            error_cids=error_cids,
            spider_state=spider_state,
        )

    def save_processed_cid(self, cid: str, state: AppState) -> bool:
        """Save a single processed CID immediately."""
        state.processed_cids.add(cid)
        return self._save_cids_to_file(state.processed_cids, self.processed_file)

    def save_error_cid(self, cid: str, state: AppState) -> bool:
        """Save a single error CID immediately."""
        state.error_cids.add(cid)
        return self._save_cids_to_file(state.error_cids, self.errors_file)

    def save_spider_state(self, spider_state: SpiderState) -> bool:
        """Save spider state immediately."""
        return self._save_spider_state(spider_state)

    def save_state(self, state: AppState) -> bool:
        """Save complete application state to disk."""
        processed_ok = self._save_cids_to_file(
            state.processed_cids, self.processed_file
        )
        errors_ok = self._save_cids_to_file(state.error_cids, self.errors_file)
        spider_ok = (
            self._save_spider_state(state.spider_state) if state.spider_state else True
        )
        return processed_ok and errors_ok and spider_ok

    def is_processed(self, cid: str, state: AppState) -> bool:
        """Check if a CID has been processed."""
        return cid in state.processed_cids

    def is_error(self, cid: str, state: AppState) -> bool:
        """Check if a CID has errored."""
        return cid in state.error_cids
