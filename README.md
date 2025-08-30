# TEZOS ARCHIVER

## Data Persistence

The tool automatically creates a `data/` folder in the source directory to store:

- **processed_cids.json**: List of successfully processed IPFS CIDs
- **errors_cids.json**: List of CIDs that failed to archive (for manual retry)


A Python command-line tool for archiving Tezos NFTs to the Wayback Machine. This tool fetches NFT metadata from Tezos wallets using the TzKT API and automatically archives IPFS-hosted artifacts to ensure long-term preservation.

## Prerequisites

- Python 3.10+
- Internet Archive account with API access
- Required Python packages (see installation)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd tz-archiver-cli
```

2. Install dependencies:
```bash
pip install requests python-dotenv wayback-utils
```

3. Create a `.env` file with your Internet Archive credentials:
```env
ARCHIVE_ACCESS=your_access_key_here
ARCHIVE_SECRET=your_secret_key_here
```

## Usage

### Basic Usage

Archive NFTs from a specific Tezos wallet:
```bash
python src/tz_archiver_cli.py -w tz1U7C2NVwbhdvG3fJixLLUWUyZHuXWNiF7V
```

### Spider Mode (Random Discovery)

Run without specifying a wallet to archive random tokens:
```bash
python src/tz_archiver_cli.py
```

### Advanced Usage

Specify a custom limit for the number of tokens to process:
```bash
python src/tz_archiver_cli.py -w tz1U7C2NVwbhdvG3fJixLLUWUyZHuXWNiF7V -l 500
```

### Command-line Options

- `-w, --wallet` (optional): Tezos wallet address (e.g., tz1...). If not provided, runs in spider mode
- `-l, --limit` (optional): Number of tokens to process (default: 10,000)
- `-h, --help`: Show help message

## How It Works

1. **Token Discovery**: The tool queries the TzKT API to find:
   - Tokens minted by the wallet
   - Tokens currently owned by the wallet
   - Tokens from contracts associated with the wallet

2. **IPFS Detection**: Scans token metadata for `artifactUri` fields containing IPFS URLs

3. **Archiving Process**: For each IPFS artifact:
   - Converts IPFS CID to HTTP URL via `ipfs.fileship.xyz`
   - Checks if already archived in Wayback Machine
   - Submits new URLs for archiving with custom parameters

4. **Concurrency Control**: Maintains up to 4 concurrent archiving processes to respect rate limits

5. **State Persistence**: All processed CIDs and errors are saved to disk in the `src/data/` folder:
   - `processed_cids.json`: Successfully processed IPFS CIDs
   - `errors_cids.json`: CIDs that failed to archive

6. **Resume Capability**: The tool automatically loads previous session data and continues from where it left off

## Configuration

### Environment Variables

- `ARCHIVE_ACCESS`: Internet Archive access key
- `ARCHIVE_SECRET`: Internet Archive secret key

### Archiving Parameters

The tool uses these Wayback Machine settings:
- `js_behavior_timeout`: 7 seconds
- `delay_wb_availability`: False
- `if_not_archived_within`: 31,536,000 seconds (1 year)

### Concurrency Settings

- `MAX_CONCURRENT_PROCESSES`: 4 (configurable in source)

## Project Structure

```
tz-archiver-cli/
├── src/
│   ├── data/                     # Persistent state storage (auto-created)
│   │   ├── processed_cids.json   # Successfully processed CIDs
│   │   └── errors_cids.json      # Failed CIDs for retry
│   ├── utils/                    # Utility modules
│   │   ├── __init__.py           # Package initialization
│   │   ├── logger.py             # Colored logging system
│   │   └── tzkt.py               # TzKT API client with typed responses
│   ├── tz_archiver_cli.py        # Main CLI application
│   └── .env                      # Environment variables (create this)
├── README.md                     # This file
└── requirements.txt              # Python dependencies (optional)
```

## API Integration

### TzKT API

The tool integrates with the [TzKT API](https://api.tzkt.io/) to fetch Tezos blockchain data:

- **Mints**: `/v1/tokens?firstMinter={address}`
- **Balances**: `/v1/tokens/balances?account={address}`
- **Contract Tokens**: `/v1/tokens?contract={address}`

### Wayback Machine API

Uses the `wayback-utils` library to interact with the Internet Archive's Save Page Now API.


## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT 

## Notes

- The tool respects rate limits with built-in delays (12 captures/minute Wayback Machine limit)
- Large collections may take significant time to process
- Internet Archive archiving is asynchronous - results may not be immediately available

---

Generated with ❤️ for the Tezos NFT community
