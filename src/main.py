"""
TZ Archiver CLI - Archive Tezos NFTs to Wayback Machine

A command-line tool for archiving Tezos NFT artifacts to the Internet Archive.
Supports wallet-specific archiving and random token discovery (spider mode).
"""

import sys
import argparse
from typing import Optional

from dotenv import load_dotenv

from config import Config
from state_manager import StateManager
from archiver import WaybackArchiver
from processor import TokenProcessor, WalletProcessor, SpiderProcessor
from utils.logger import Logger


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="tz-archiver-cli",
        description="Archive Tezos NFTs to Wayback Machine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -w tz1ABC123...                    # Archive specific wallet
  %(prog)s -w tz1ABC123... -l 500            # Limit to 500 tokens
  %(prog)s                                   # Spider mode (random discovery)

For more information, visit: https://github.com/your-repo/tz-archiver-cli
        """,
    )

    parser.add_argument(
        "-w",
        "--wallet",
        type=str,
        help="Tezos wallet address (e.g., tz1...). If not provided, runs in spider mode",
    )

    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=Config.DEFAULT_TOKEN_LIMIT,
        help=f"Number of tokens to process (default: {Config.DEFAULT_TOKEN_LIMIT:,})",
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {Config.VERSION}"
    )

    return parser


def validate_arguments(args: argparse.Namespace) -> bool:
    """Validate command-line arguments."""
    if args.wallet and not args.wallet.startswith(("tz1", "tz2", "tz3", "KT1")):
        print(
            "Error: Invalid Tezos address format. Must start with tz1, tz2, tz3, or KT1"
        )
        return False

    if args.limit < 1:
        print("Error: Limit must be a positive integer")
        return False

    return True


def check_credentials() -> tuple[Optional[str], Optional[str]]:
    """Check and validate Internet Archive credentials."""
    access_key, secret_key = Config.get_archive_credentials()

    if not access_key or not secret_key:
        print("Error: Missing Internet Archive credentials")
        print("Please set ARCHIVE_ACCESS and ARCHIVE_SECRET environment variables")
        print("You can create a .env file with:")
        print("ARCHIVE_ACCESS=your_access_key")
        print("ARCHIVE_SECRET=your_secret_key")
        return None, None

    return access_key, secret_key


def setup_components() -> tuple[StateManager, WaybackArchiver, TokenProcessor]:
    """Initialize and return all required components."""
    # Validate credentials
    access_key, secret_key = check_credentials()
    if not access_key or not secret_key:
        sys.exit(1)

    # Initialize components
    state_manager = StateManager()
    archiver = WaybackArchiver(access_key, secret_key)
    processor = TokenProcessor(archiver, state_manager)

    return state_manager, archiver, processor


def run_wallet_mode(wallet_address: str, limit: int) -> None:
    """Run the application in wallet processing mode."""
    logger = Logger("CLI")

    try:
        # Setup components
        state_manager, archiver, processor = setup_components()

        # Load state
        state = state_manager.load_state()

        # Create wallet processor and run
        wallet_processor = WalletProcessor(processor)
        stats = wallet_processor.process_wallet(wallet_address, limit, state)

        # Display final statistics
        logger.success(f"Processing complete: {stats}")

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


def run_spider_mode() -> None:
    """Run the application in spider mode (random token discovery)."""
    logger = Logger("CLI")

    try:
        # Setup components
        state_manager, archiver, processor = setup_components()

        # Load state
        state = state_manager.load_state()

        # Create spider processor and run
        spider_processor = SpiderProcessor(processor)
        spider_processor.run_spider_mode(state)

    except KeyboardInterrupt:
        logger.info("Spider mode interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error in spider mode: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI application."""
    # Load environment variables
    load_dotenv()

    # Parse arguments
    parser = create_argument_parser()
    args = parser.parse_args()

    # Validate arguments
    if not validate_arguments(args):
        sys.exit(1)

    # Initialize logger
    logger = Logger("CLI")
    logger.info(f"Starting {Config.APP_NAME} v{Config.VERSION}")

    # Run appropriate mode
    if args.wallet:
        run_wallet_mode(args.wallet, args.limit)
    else:
        logger.warning("No wallet address provided")
        run_spider_mode()


if __name__ == "__main__":
    main()
