"""
Main processing module for TZ Archiver CLI.
Handles token discovery, filtering, and orchestrates the archiving process.
"""

import time
import hashlib
from typing import List, Optional, Callable, Deque
from dataclasses import dataclass
from collections import deque

from utils.tzkt import (
    Token,
    mints,
    balances,
    contract_tokens,
    random_tokens,
    block_count,
    tokens,
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
    """Processes tokens using deterministic coverage algorithm."""

    def __init__(self, processor: TokenProcessor, state_manager: StateManager):
        self.processor = processor
        self.state_manager = state_manager

        # Deterministic walk parameters - will be loaded/initialized
        self.total_token_space = None
        self.current_position = None
        self.step_size = None
        self.start_position = None
        self.tokens_visited = 0
        self.seed_data = None

        # Large prime numbers for step size to ensure good coverage
        self.prime_steps = [
            7919,
            12911,
            15073,
            18443,
            20399,
            22447,
            25013,
            27697,
            30089,
            32609,
            35171,
            37549,
            40009,
            42589,
            45121,
            47737,
        ]

    def _load_spider_state(self, state: AppState) -> bool:
        """Load spider state from persistent storage."""
        spider_state = state.spider_state

        if spider_state and spider_state.current_position is not None:
            # Resume from saved state
            self.total_token_space = spider_state.total_token_space
            self.current_position = spider_state.current_position
            self.step_size = spider_state.step_size
            self.start_position = spider_state.start_position
            self.tokens_visited = spider_state.tokens_visited
            self.seed_data = spider_state.seed_data

            logger.success("Resuming spider mode from previous session:")
            logger.info(f"   • Token space: {self.total_token_space:,}")
            logger.info(f"   • Current position: {self.current_position:,}")
            logger.info(f"   • Start position: {self.start_position:,}")
            logger.info(f"   • Step size: {self.step_size:,}")
            logger.info(f"   • Tokens visited: {self.tokens_visited:,}")

            if self.total_token_space and self.tokens_visited > 0:
                coverage = (self.tokens_visited / self.total_token_space) * 100
                logger.info(f"   • Previous coverage: {coverage:.2f}%")

            return True
        else:
            logger.info("🆕 No previous spider session found - starting fresh")
            return False

    def _save_spider_state(self, state: AppState) -> None:
        """Save current spider state to persistent storage."""
        if state.spider_state is None:
            from state_manager import SpiderState

            state.spider_state = SpiderState()

        # Update the spider state
        state.spider_state.total_token_space = self.total_token_space
        state.spider_state.current_position = self.current_position
        state.spider_state.step_size = self.step_size
        state.spider_state.start_position = self.start_position
        state.spider_state.tokens_visited = self.tokens_visited
        state.spider_state.seed_data = self.seed_data

        # Save to disk
        self.state_manager.save_spider_state(state.spider_state)

    def _initialize_walk_parameters(self, state: AppState) -> bool:
        """Initialize parameters for deterministic walk."""
        # First try to load from previous session
        if self._load_spider_state(state):
            return True

        # If no previous state, initialize fresh
        logger.info("🔧 Initializing deterministic coverage algorithm...")

        try:
            # Get total token count from TzKT API
            total_tokens = block_count()  # This gives us a rough upper bound
            if not total_tokens:
                logger.warning("Could not get block count, using hardcoded estimate")
                total_tokens = 6_000_000  # Fallback to hardcoded estimate

            # Use a reasonable token space (tokens with artifacts are a subset)
            self.total_token_space = min(total_tokens, 6_000_000)

            # Generate unique start position based on machine/time
            import platform
            import os

            self.seed_data = f"{platform.node()}{os.getpid()}{int(time.time())}"
            hash_digest = hashlib.md5(self.seed_data.encode()).hexdigest()
            seed = int(hash_digest[:8], 16)

            # Random start position based on unique seed
            self.start_position = seed % self.total_token_space
            self.current_position = self.start_position

            # Select prime step size based on seed
            step_index = seed % len(self.prime_steps)
            self.step_size = self.prime_steps[step_index]

            # Reset visited counter for new session
            self.tokens_visited = 0

            logger.info(f"🎯 Coverage algorithm initialized:")
            logger.info(f"   • Token space: {self.total_token_space:,}")
            logger.info(f"   • Start position: {self.start_position:,}")
            logger.info(f"   • Step size: {self.step_size:,}")
            logger.info(
                f"   • Estimated full coverage: {self.total_token_space // Config.DEFAULT_SPIDER_BATCH_SIZE:,} iterations"
            )

            # Save initial state
            self._save_spider_state(state)

            return True

        except Exception as e:
            logger.error(f"Failed to initialize walk parameters: {e}")
            return False

    def _get_next_batch_offset(self, state: AppState) -> int:
        """Calculate next offset using deterministic walk."""
        if self.current_position is None:
            if not self._initialize_walk_parameters(state):
                # Fallback to random if initialization fails
                import random

                return random.randint(0, 6_000_000)

        # Get current position
        offset = self.current_position

        # Calculate next position using modular arithmetic
        self.current_position = (
            self.current_position + self.step_size
        ) % self.total_token_space
        self.tokens_visited += 1

        # Save updated state after each step
        self._save_spider_state(state)

        # Check if we've completed a full cycle
        if self.current_position == self.start_position and self.tokens_visited > 1:
            logger.success(
                f"🎉 Full coverage cycle completed! Visited {self.tokens_visited:,} positions"
            )
            logger.info("🔄 Starting new cycle with different step size...")

            # Start new cycle with different parameters
            self.tokens_visited = 0
            # Use next prime step size
            current_index = self.prime_steps.index(self.step_size)
            next_index = (current_index + 1) % len(self.prime_steps)
            self.step_size = self.prime_steps[next_index]
            logger.info(f"📐 New step size: {self.step_size:,}")

        return offset

    def _get_deterministic_tokens(
        self, batch_size: int, state: AppState
    ) -> Optional[List[Token]]:
        """Fetch tokens using deterministic position."""
        offset = self._get_next_batch_offset(state)

        # Use the dedicated function from tzkt.py
        return tokens(batch_size, offset)

    def _log_coverage_stats(self, iteration: int, stats) -> None:
        """Log detailed coverage statistics."""
        if self.total_token_space and self.tokens_visited > 0:
            coverage_percentage = (self.tokens_visited / self.total_token_space) * 100

            logger.info(f"📊 Coverage Stats (Iteration {iteration}):")
            logger.info(
                f"   • Position: {self.current_position:,}/{self.total_token_space:,}"
            )
            logger.info(f"   • Coverage: {coverage_percentage:.2f}%")
            logger.info(f"   • Step size: {self.step_size:,}")
            logger.info(f"   • {stats}")

    def run_spider_mode(self, state: AppState) -> None:
        """
        Run deterministic spider mode for systematic token discovery.

        This algorithm ensures:
        1. Each user starts at a different random position
        2. Follows a deterministic path that covers the entire space
        3. Eventually visits every token in the database
        4. Minimizes redundant discoveries after initial coverage

        Args:
            state: Current application state
        """
        logger.warning(
            "🕷️ Starting deterministic spider mode - systematic token coverage"
        )

        # Initialize the deterministic walk
        if not self._initialize_walk_parameters(state):
            logger.error(
                "Failed to initialize coverage algorithm, falling back to basic mode"
            )
            self._run_fallback_spider_mode(state)
            return

        iteration = 0
        consecutive_empty_batches = 0
        max_empty_batches = 5

        try:
            while True:
                iteration += 1
                logger.info(f"Deterministic iteration {iteration}")

                # Get tokens using deterministic algorithm
                tokens = self._get_deterministic_tokens(
                    Config.DEFAULT_SPIDER_BATCH_SIZE, state
                )

                if not tokens:
                    consecutive_empty_batches += 1
                    logger.warning(
                        f"⚠️ No tokens returned (attempt {consecutive_empty_batches}/{max_empty_batches})"
                    )

                    if consecutive_empty_batches >= max_empty_batches:
                        logger.warning("Too many empty batches, adjusting position...")
                        # Jump to a different area
                        self.current_position = (
                            self.current_position + self.total_token_space // 4
                        ) % self.total_token_space
                        consecutive_empty_batches = 0
                        # Save state after position adjustment
                        self._save_spider_state(state)

                    time.sleep(Config.DEFAULT_SPIDER_DELAY * 2)
                    continue

                # Reset empty batch counter on success
                consecutive_empty_batches = 0

                # Process tokens
                stats = self.processor.process_tokens(tokens, state)

                # Log detailed coverage statistics
                self._log_coverage_stats(iteration, stats)

                # Brief pause between iterations
                time.sleep(Config.DEFAULT_SPIDER_DELAY)

        except KeyboardInterrupt:
            logger.info("🛑 Deterministic spider mode interrupted by user")
            final_coverage = (
                (self.tokens_visited / self.total_token_space) * 100
                if self.total_token_space
                else 0
            )
            logger.info(f"📈 Final coverage achieved: {final_coverage:.2f}%")
        except Exception as e:
            logger.error(f"Error in deterministic spider mode: {e}")
            time.sleep(Config.DEFAULT_SPIDER_DELAY * 2)

    def _run_fallback_spider_mode(self, state: AppState) -> None:
        """Fallback to basic random mode if deterministic fails."""
        logger.warning("🔄 Running fallback random spider mode")

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
