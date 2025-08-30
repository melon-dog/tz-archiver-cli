"""
Main processing module for TZ Archiver CLI.
Handles token discovery, filtering, and orchestrates the archiving process.
"""

import time
from typing import List, Optional, Callable, Deque
from dataclasses import dataclass
from collections import deque

from utils.tzkt import Token, mints, balances, contract_tokens, random_tokens
from archiver import WaybackArchiver, ArchiveResult
from state_manager import StateManager, AppState
from config import Config
from utils.logger import Logger


logger = Logger("Processor")


class RateLimiter:
    """Rate limiter to control requests per minute."""

    def __init__(self, max_requests_per_minute: int):
        self.max_requests = max_requests_per_minute
        self.request_times: Deque[float] = deque()
        self.window_seconds = 60.0  # 1 minute window

    def _cleanup_old_requests(self) -> None:
        """Remove request timestamps older than the time window."""
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds

        while self.request_times and self.request_times[0] < cutoff_time:
            self.request_times.popleft()

    def can_make_request(self) -> bool:
        """Check if a request can be made without exceeding the rate limit."""
        self._cleanup_old_requests()
        return len(self.request_times) < self.max_requests

    def wait_if_needed(self) -> None:
        """Wait if necessary to respect the rate limit."""
        self._cleanup_old_requests()

        if len(self.request_times) >= self.max_requests:
            # Calculate how long to wait until the oldest request expires
            oldest_request_time = self.request_times[0]
            wait_time = (oldest_request_time + self.window_seconds) - time.time()

            if wait_time > 0:
                logger.warning(
                    f"Rate limit reached ({self.max_requests}/min). "
                    f"Waiting {wait_time:.1f} seconds...",
                    timestamp=False,
                )
                time.sleep(wait_time)
                # Clean up again after waiting
                self._cleanup_old_requests()

    def record_request(self) -> None:
        """Record that a request was made."""
        self.request_times.append(time.time())

    def get_current_rate(self) -> int:
        """Get the current number of requests in the time window."""
        self._cleanup_old_requests()
        return len(self.request_times)

    def get_time_until_next_slot(self) -> float:
        """Get time in seconds until next request slot is available."""
        self._cleanup_old_requests()

        if len(self.request_times) < self.max_requests:
            return 0.0

        oldest_request_time = self.request_times[0]
        return max(0.0, (oldest_request_time + self.window_seconds) - time.time())


@dataclass
class ProcessingStats:
    """Statistics for a processing session."""

    total_tokens: int = 0
    processed_cids: int = 0
    skipped_cids: int = 0
    successful_archives: int = 0
    failed_archives: int = 0
    already_archived: int = 0

    def __str__(self) -> str:
        """String representation of stats."""
        return (
            f"Tokens: {self.total_tokens}, "
            f"Processed: {self.processed_cids}, "
            f"Skipped: {self.skipped_cids}, "
            f"Successful: {self.successful_archives}, "
            f"Failed: {self.failed_archives}, "
            f"Already archived: {self.already_archived}"
        )


class TokenProcessor:
    """Main processor for tokens and archiving."""

    def __init__(self, archiver: WaybackArchiver, state_manager: StateManager):
        self.archiver = archiver
        self.state_manager = state_manager
        self.stats = ProcessingStats()
        # Initialize rate limiter with the configured limit
        self.rate_limiter = RateLimiter(Config.WAYBACK_RATE_LIMIT)
        logger.info(
            f"Rate limiter initialized: {Config.WAYBACK_RATE_LIMIT} requests/minute"
        )

    def _extract_ipfs_cids(self, tokens: List[Token]) -> List[str]:
        """Extract IPFS CIDs from token metadata."""
        cids = []
        for token in tokens:
            if (
                token.metadata
                and token.metadata.artifactUri
                and token.metadata.artifactUri.startswith("ipfs://")
            ):
                cid = token.metadata.artifactUri.replace("ipfs://", "")
                cids.append(cid)
        return cids

    def _create_archive_callback(
        self, cid: str, state: AppState
    ) -> Callable[[ArchiveResult], None]:
        """Create callback function for archive completion."""

        def on_archive_complete(result: ArchiveResult) -> None:
            if result.success:
                self.state_manager.save_processed_cid(cid, state)
                # Note: already_archived case is handled before this callback
                # so this is always a successful archive operation
                self.stats.successful_archives += 1
            else:
                self.state_manager.save_error_cid(cid, state)
                self.stats.failed_archives += 1

        return on_archive_complete

    def _archive_cid_with_rate_limit(self, cid: str, state: AppState) -> None:
        """Archive a CID while respecting rate limits."""
        logger.info(f"Processing CID: {cid}")

        # First check if already archived (this doesn't count for rate limit)
        if self.archiver.is_already_archived(cid):
            logger.success("Already archived")
            self.stats.already_archived += 1
            self.state_manager.save_processed_cid(cid, state)
            return

        # Only apply rate limiting for actual archiving requests
        self.rate_limiter.wait_if_needed()

        # Log current rate status
        current_rate = self.rate_limiter.get_current_rate()
        logger.info(
            f"Archiving CID (rate: {current_rate}/{Config.WAYBACK_RATE_LIMIT}/min): {cid}",
            timestamp=False,
        )

        # Record that we're making a request (only for actual archiving)
        self.rate_limiter.record_request()

        # Create callback and submit for archiving
        callback = self._create_archive_callback(cid, state)
        self.archiver.archive_cid(cid, on_complete=callback)

    def process_tokens(self, tokens: List[Token], state: AppState) -> ProcessingStats:
        """
        Process a list of tokens and archive their IPFS artifacts.

        Args:
            tokens: List of tokens to process
            state: Current application state

        Returns:
            Processing statistics
        """
        self.stats = ProcessingStats()
        self.stats.total_tokens = len(tokens)

        logger.info(f"Processing {len(tokens)} tokens")

        # Extract IPFS CIDs
        cids = self._extract_ipfs_cids(tokens)
        logger.info(f"Found {len(cids)} IPFS artifacts")

        # Process each CID
        for cid in cids:
            if self.state_manager.is_processed(cid, state):
                logger.warning(f"Already processed CID: {cid}")
                self.stats.skipped_cids += 1
                continue

            self.stats.processed_cids += 1
            # Use rate-limited archiving method
            self._archive_cid_with_rate_limit(cid, state)

        return self.stats


class WalletProcessor:
    """Processes tokens from a specific wallet."""

    def __init__(self, processor: TokenProcessor):
        self.processor = processor

    def process_wallet(
        self, wallet_address: str, limit: int, state: AppState
    ) -> ProcessingStats:
        """
        Process all tokens associated with a wallet.

        Args:
            wallet_address: Tezos wallet address
            limit: Maximum number of tokens to fetch
            state: Current application state

        Returns:
            Processing statistics
        """
        logger.info(f"Processing wallet: {wallet_address}")
        logger.info(f"Token limit: {limit}")

        # Fetch tokens from different sources
        logger.info("Fetching minted tokens...")
        wallet_mints = mints(wallet_address, None, limit, 0)

        logger.info("Fetching owned tokens...")
        wallet_balances = balances(wallet_address, limit, 0)

        logger.info("Fetching contract tokens...")
        wallet_contract_tokens = contract_tokens(wallet_address, limit, 0)

        # Combine all tokens
        all_tokens: List[Token] = []
        if wallet_mints:
            all_tokens.extend(wallet_mints)
            logger.info(f"Found {len(wallet_mints)} minted tokens")

        if wallet_balances:
            all_tokens.extend(wallet_balances)
            logger.info(f"Found {len(wallet_balances)} owned tokens")

        if wallet_contract_tokens:
            all_tokens.extend(wallet_contract_tokens)
            logger.info(f"Found {len(wallet_contract_tokens)} contract tokens")

        # Remove duplicates based on token ID and contract
        unique_tokens = []
        seen = set()
        for token in all_tokens:
            key = (token.contract.address if token.contract else None, token.tokenId)
            if key not in seen:
                seen.add(key)
                unique_tokens.append(token)

        logger.info(f"Total unique tokens: {len(unique_tokens)}")

        return self.processor.process_tokens(unique_tokens, state)


class SpiderProcessor:
    """Processes random tokens in spider mode."""

    def __init__(self, processor: TokenProcessor):
        self.processor = processor

    def run_spider_mode(self, state: AppState) -> None:
        """
        Run continuous spider mode for random token discovery.

        Args:
            state: Current application state
        """
        logger.warning("Starting spider mode - continuous random token discovery")

        iteration = 0
        while True:
            iteration += 1
            logger.info(f"Spider iteration {iteration}")

            try:
                # Fetch random tokens
                tokens = random_tokens(Config.DEFAULT_SPIDER_BATCH_SIZE)
                if not tokens:
                    logger.warning("No tokens returned from random API")
                    time.sleep(Config.DEFAULT_SPIDER_DELAY)
                    continue

                # Process tokens
                stats = self.processor.process_tokens(tokens, state)
                logger.info(f"Spider stats: {stats}")

                # Brief pause between iterations
                time.sleep(Config.DEFAULT_SPIDER_DELAY)

            except KeyboardInterrupt:
                logger.info("Spider mode interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in spider mode: {e}")
                time.sleep(Config.DEFAULT_SPIDER_DELAY * 2)  # Longer pause on error
