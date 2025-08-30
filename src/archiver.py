"""
Wayback Machine archiver module.
Handles archiving of URLs to the Internet Archive with proper concurrency control.
"""

import time
import threading
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
    """Manages concurrent processing limits with thread safety."""

    def __init__(self, max_concurrent: int = Config.MAX_CONCURRENT_PROCESSES):
        self.max_concurrent = max_concurrent
        self.current_count = 0
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """
        Acquire a processing slot, waiting if necessary.
        Returns True if slot acquired, False if timeout.
        """
        timeout_seconds = 120  # Maximum wait time
        start_time = time.time()

        while True:
            with self._lock:
                if self.current_count < self.max_concurrent:
                    self.current_count += 1
                    logger.info(
                        f"Slot acquired ({self.current_count}/{self.max_concurrent})"
                    )
                    return True

            # Check for timeout
            if time.time() - start_time > timeout_seconds:
                logger.error(
                    f"Timeout waiting for available slot after {timeout_seconds}s"
                )
                return False

            logger.warning(
                f"Waiting for available slot ({self.current_count}/{self.max_concurrent})"
            )
            time.sleep(1)

    def release(self) -> None:
        """Release a processing slot."""
        with self._lock:
            if self.current_count > 0:
                self.current_count -= 1
                logger.info(
                    f"Slot released ({self.current_count}/{self.max_concurrent})"
                )

    @property
    def available_slots(self) -> int:
        """Get number of available processing slots."""
        with self._lock:
            return max(0, self.max_concurrent - self.current_count)

    def get_status(self) -> str:
        """Get current status string."""
        with self._lock:
            return f"{self.current_count}/{self.max_concurrent} slots in use"


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

        logger.info(f"Requesting slot for archiving: {normalized_cid}")

        # Try to acquire a slot with timeout
        if not self.concurrency_manager.acquire():
            # Timeout occurred
            error_msg = f"Failed to acquire processing slot for {normalized_cid}"
            logger.error(error_msg)
            if on_complete:
                result = ArchiveResult(
                    cid=normalized_cid,
                    success=False,
                    already_archived=False,
                    error=error_msg,
                )
                on_complete(result)
            return

        logger.info(f"Submitting for archiving: {normalized_cid}")

        def on_save_end(status: WayBackStatus) -> None:
            """Handle archiving completion."""
            try:
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
            finally:
                # Always release the slot, even if callback fails
                self.concurrency_manager.release()

        try:
            save_data = self.wayback.save(
                url,
                timeout=60,
                js_behavior_timeout=Config.WAYBACK_JS_TIMEOUT,
                delay_wb_availability=Config.WAYBACK_DELAY_AVAILABILITY,
                if_not_archived_within=Config.WAYBACK_IF_NOT_ARCHIVED_WITHIN,
                on_result=on_save_end,
            )
            if save_data.job_id is None:
                if save_data.message is not None:
                    logger.error(f"Failed to submit for archiving: {save_data.message}")
                else:
                    logger.error(f"Failed to submit for archiving")
                self.concurrency_manager.release()

        except Exception as e:
            # Release slot immediately on exception
            self.concurrency_manager.release()
            error_msg = f"Failed to submit for archiving: {e}"
            logger.error(error_msg)
            if on_complete:
                result = ArchiveResult(
                    cid=normalized_cid,
                    success=False,
                    already_archived=False,
                    error=error_msg,
                )
                on_complete(result)
