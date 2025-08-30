"""
Wayback Machine archiver module.
Handles archiving of URLs to the Internet Archive with proper concurrency control.
"""

import time
from typing import Callable, Optional
from dataclasses import dataclass

from wayback_utils import WayBack, WayBackStatus

from config import Config
from utils.logger import Logger


logger = Logger("Archiver")


@dataclass
class ArchiveResult:
    """Result of an archive operation."""

    cid: str
    success: bool
    already_archived: bool
    message: Optional[str] = None
    error: Optional[str] = None


class ConcurrencyManager:
    """Manages concurrent processing limits."""

    def __init__(self, max_concurrent: int = Config.MAX_CONCURRENT_PROCESSES):
        self.max_concurrent = max_concurrent
        self.current_count = 0

    def acquire(self) -> None:
        """Acquire a processing slot, waiting if necessary."""
        while self.current_count >= self.max_concurrent:
            time.sleep(1)
        self.current_count += 1

    def release(self) -> None:
        """Release a processing slot."""
        if self.current_count > 0:
            self.current_count -= 1

    @property
    def available_slots(self) -> int:
        """Get number of available processing slots."""
        return max(0, self.max_concurrent - self.current_count)


class WaybackArchiver:
    """Handles archiving to the Wayback Machine."""

    def __init__(self, access_key: str, secret_key: str):
        self.wayback = WayBack(access_key, secret_key)
        self.concurrency_manager = ConcurrencyManager()

    def _normalize_cid(self, cid: str) -> str:
        """Normalize IPFS CID by removing ipfs:// prefix."""
        return cid.replace("ipfs://", "")

    def _build_ipfs_url(self, cid: str) -> str:
        """Build IPFS gateway URL from CID."""
        normalized_cid = self._normalize_cid(cid)
        return f"{Config.IPFS_GATEWAY}/{normalized_cid}"

    def is_already_archived(self, cid: str) -> bool:
        """Check if a CID is already archived in Wayback Machine."""
        try:
            url = self._build_ipfs_url(cid)
            return self.wayback.indexed(url)
        except Exception as e:
            logger.error(f"Failed to check archive status for {cid}: {e}")
            return False

    def archive_cid(
        self, cid: str, on_complete: Optional[Callable[[ArchiveResult], None]] = None
    ) -> None:
        """
        Archive a CID to Wayback Machine.

        Note: This method assumes the CID is not already archived.
        Use is_already_archived() first to check before calling this method.

        Args:
            cid: IPFS CID to archive
            on_complete: Callback function called when archiving completes
        """
        normalized_cid = self._normalize_cid(cid)
        url = self._build_ipfs_url(normalized_cid)

        logger.info(f"Submitting for archiving: {normalized_cid}")

        # Wait for available slot and acquire it
        while (
            self.concurrency_manager.current_count
            >= self.concurrency_manager.max_concurrent
        ):
            logger.warning(f"Waiting for available slot (CID: {normalized_cid})")
            time.sleep(1)

        self.concurrency_manager.acquire()
        logger.info("Archiving to Wayback Machine...")

        def on_save_end(status: WayBackStatus) -> None:
            """Handle archiving completion."""
            self.concurrency_manager.release()

            if status.message:
                logger.info(f"Message: {status.message}")

            result = ArchiveResult(
                cid=normalized_cid,
                success=status.status == "success",
                already_archived=False,
                message=status.message,
            )

            if status.status == "success":
                logger.success("Successfully archived")
            elif status.status == "pending":
                logger.warning("Archiving in progress...")
                result.success = True  # Pending is considered success
            elif status.status == "error":
                logger.error("Failed to archive")
                result.error = status.message

            if on_complete:
                on_complete(result)

        try:
            self.wayback.save(
                url,
                js_behavior_timeout=Config.WAYBACK_JS_TIMEOUT,
                delay_wb_availability=Config.WAYBACK_DELAY_AVAILABILITY,
                if_not_archived_within=Config.WAYBACK_IF_NOT_ARCHIVED_WITHIN,
                on_result=on_save_end,
            )
        except Exception as e:
            self.concurrency_manager.release()
            logger.error(f"Failed to submit for archiving: {e}")
            if on_complete:
                result = ArchiveResult(
                    cid=normalized_cid,
                    success=False,
                    already_archived=False,
                    error=str(e),
                )
                on_complete(result)
