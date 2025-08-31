"""
Main processing module for TZ Archiver CLI.
Handles token discovery, filtering, and orchestrates the archiving process.
"""

import time
import random
from typing import List, Optional, Callable, Deque
from dataclasses import dataclass
from collections import deque

from utils.tzkt import (
    Token,
    mints,
    balances,
    contract_tokens,
    random_tokens,
    tokens,
    HARDCODED_CURRENT_TOKENS_WITH_ARTIFACTS,
)
from archiver import WaybackArchiver, ArchiveResult
from state_manager import StateManager, AppState, SpiderState
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
                    f"Waiting {wait_time:.1f} seconds..."
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
            f"Archiving CID (rate: {current_rate}/{Config.WAYBACK_RATE_LIMIT}/min): {cid}"
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
    """Processes tokens using bidirectional exploration algorithm."""

    def __init__(self, processor: TokenProcessor, state_manager: StateManager):
        self.processor = processor
        self.state_manager = state_manager

        # Bidirectional algorithm state - will be loaded/initialized
        self.seed = None
        self.iteration_count = 0
        self.is_positive_direction = True
        self.max_tokens = HARDCODED_CURRENT_TOKENS_WITH_ARTIFACTS
        self.batch_size = Config.DEFAULT_SPIDER_BATCH_SIZE

    def _load_spider_state(self, state: AppState) -> bool:
        """Load spider state from persistent storage."""
        spider_state = state.spider_state

        if spider_state and spider_state.seed is not None:
            # Resume from saved state
            self.seed = spider_state.seed
            self.iteration_count = spider_state.iteration_count or 0
            self.is_positive_direction = (
                spider_state.is_positive_direction
                if spider_state.is_positive_direction is not None
                else True
            )

            logger.success("Resuming spider mode from previous session:")
            logger.info(f"   • Exploration seed: {self.seed:,}")
            logger.info(f"   • Iteration count: {self.iteration_count:,}")
            logger.info(
                f"   • Direction: {'positive' if self.is_positive_direction else 'negative'}"
            )
            logger.info(f"   • Token space: {self.max_tokens:,}")
            logger.info(f"   • Batch size: {self.batch_size}")

            return True
        else:
            logger.info("No previous spider session found - starting fresh")
            return False

    def _save_spider_state(self, state: AppState) -> None:
        """Save current spider state to persistent storage."""
        if state.spider_state is None:
            from state_manager import SpiderState

            state.spider_state = SpiderState()

        # Update the spider state with new simplified fields
        state.spider_state.seed = self.seed
        state.spider_state.iteration_count = self.iteration_count
        state.spider_state.is_positive_direction = self.is_positive_direction

        # Save to disk
        self.state_manager.save_spider_state(state.spider_state)

    def _initialize_spider_parameters(self, state: AppState) -> bool:
        """Initialize parameters for bidirectional exploration."""
        # First try to load from previous session
        if self._load_spider_state(state):
            return True

        # If no previous state, initialize fresh
        logger.info("Initializing exploration algorithm...")

        try:
            # Generate random seed in the middle range of token space
            # This avoids starting at the very beginning or end
            upper_bound = int(self.max_tokens * 0.75)
            lower_bound = int(self.max_tokens * 0.25)
            self.seed = random.randint(lower_bound, upper_bound)

            # Start fresh
            self.iteration_count = 0
            self.is_positive_direction = True

            logger.info("Exploration initialized:")
            logger.info(f"   • Token space: {self.max_tokens:,}")
            logger.info(f"   • Exploration seed: {self.seed:,}")
            logger.info(f"   • Batch size: {self.batch_size}")
            logger.info(f"   • Starting direction: positive")

            # Save initial state
            self._save_spider_state(state)

            return True

        except Exception as e:
            logger.error(f"Failed to initialize spider parameters: {e}")
            return False

    def _generate_random_seed(self) -> int:
        """Generate a random seed in the middle range of token space."""
        upper_bound = int(self.max_tokens * 0.75)
        lower_bound = int(self.max_tokens * 0.25)
        return random.randint(lower_bound, upper_bound)

    def _get_next_token_offset(self, state: AppState) -> int:
        """
        Calculate next offset using bidirectional exploration.

        This algorithm:
        1. Starts from a random seed position
        2. Alternates between positive and negative directions
        3. Gradually explores outward from the seed
        4. Ensures systematic coverage without complex mathematics
        """
        if self.seed is None:
            if not self._initialize_spider_parameters(state):
                # Fallback to random if initialization fails
                return random.randint(0, self.max_tokens)

        # Calculate offset distance based on iteration count
        offset_distance = self.iteration_count * self.batch_size

        if self.is_positive_direction:
            # Positive direction: seed + (iteration * batch_size)
            target_offset = self.seed + offset_distance

            # Switch to negative direction for next iteration
            self.is_positive_direction = False
        else:
            # Negative direction: seed - (iteration * batch_size)
            target_offset = self.seed - offset_distance

            # Handle underflow by wrapping to the end
            if target_offset < 0:
                target_offset = (
                    self.max_tokens + target_offset
                )  # target_offset is negative

            # Switch to positive direction and increment iteration for next time
            self.is_positive_direction = True
            self.iteration_count += 1

        # Handle overflow by wrapping to the beginning
        if target_offset >= self.max_tokens:
            target_offset = target_offset - self.max_tokens

        # Save state after calculating next position
        self._save_spider_state(state)

        return target_offset

    def _get_bidirectional_tokens(
        self, batch_size: int, state: AppState
    ) -> Optional[List[Token]]:
        """Fetch tokens using bidirectional exploration."""
        offset = self._get_next_token_offset(state)

        # Use the dedicated function from tzkt.py
        return tokens(batch_size, offset)

    def _log_exploration_stats(self, iteration: int, stats, offset: int) -> None:
        """Log detailed exploration statistics."""
        logger.info(f"Exploration Stats (Iteration {iteration}):")
        logger.info(f"   • Target offset: {offset:,}")
        logger.info(f"   • Exploration seed: {self.seed:,}")
        logger.info(f"   • Iteration count: {self.iteration_count:,}")
        logger.info(
            f"   • Current direction: {'positive' if self.is_positive_direction else 'negative'}"
        )
        logger.info(f"   • {stats}")

    def run_spider_mode(self, state: AppState) -> None:
        """
        Run bidirectional spider mode for systematic token discovery.

        This algorithm:
        1. Starts from a random seed position in the middle range
        2. Alternates between positive and negative directions
        3. Explores outward systematically with each iteration
        4. Simple, predictable, and efficient coverage pattern

        Args:
            state: Current application state
        """
        logger.info("Starting bidirectional spider mode - systematic exploration")

        # Initialize the bidirectional exploration
        if not self._initialize_spider_parameters(state):
            logger.error(
                "Failed to initialize spider algorithm, falling back to random mode"
            )
            self._run_fallback_spider_mode(state)
            return

        iteration = 0
        consecutive_empty_batches = 0
        max_empty_batches = 5

        try:
            while True:
                iteration += 1
                logger.info(f"Exploration iteration {iteration}")

                # Store current offset for logging
                current_offset = self.seed + (
                    self.iteration_count * self.batch_size
                    if self.is_positive_direction
                    else -(self.iteration_count * self.batch_size)
                )

                # Get tokens using bidirectional exploration
                fetched_tokens = self._get_bidirectional_tokens(self.batch_size, state)

                if not fetched_tokens:
                    consecutive_empty_batches += 1
                    logger.warning(
                        f"No tokens returned (attempt {consecutive_empty_batches}/{max_empty_batches})"
                    )

                    if consecutive_empty_batches >= max_empty_batches:
                        logger.warning("Too many empty batches, generating new seed...")
                        # Generate new random seed to explore different area
                        self.seed = self._generate_random_seed()
                        self.iteration_count = 0
                        self.is_positive_direction = True
                        consecutive_empty_batches = 0
                        # Save state after seed reset
                        self._save_spider_state(state)
                        logger.info(f"New exploration seed: {self.seed:,}")

                    time.sleep(Config.DEFAULT_SPIDER_DELAY * 2)
                    continue

                # Reset empty batch counter on success
                consecutive_empty_batches = 0

                # Process tokens
                stats = self.processor.process_tokens(fetched_tokens, state)

                # Log detailed exploration statistics
                self._log_exploration_stats(iteration, stats, current_offset)

                # Brief pause between iterations
                time.sleep(Config.DEFAULT_SPIDER_DELAY)

        except KeyboardInterrupt:
            logger.info("Spider mode interrupted by user")
            logger.info(
                f"Final state - Seed: {self.seed:,}, Iteration: {self.iteration_count:,}"
            )
        except Exception as e:
            logger.error(f"Error in spider mode: {e}")
            time.sleep(Config.DEFAULT_SPIDER_DELAY * 2)

    def _run_fallback_spider_mode(self, state: AppState) -> None:
        """Fallback to basic random mode if deterministic fails."""
        logger.warning("Running fallback random spider mode")

        iteration = 0
        while True:
            iteration += 1
            logger.info(f"Random iteration {iteration}")

            try:
                # Use original random tokens method
                tokens = random_tokens(Config.DEFAULT_SPIDER_BATCH_SIZE)
                if not tokens:
                    logger.warning("No tokens returned from random API")
                    time.sleep(Config.DEFAULT_SPIDER_DELAY)
                    continue

                # Process tokens
                stats = self.processor.process_tokens(tokens, state)
                logger.info(f"Random stats: {stats}")

                time.sleep(Config.DEFAULT_SPIDER_DELAY)

            except KeyboardInterrupt:
                logger.info("Random spider mode interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in random spider mode: {e}")
                time.sleep(Config.DEFAULT_SPIDER_DELAY * 2)
