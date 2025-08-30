# Technical Documentation

## Architecture Overview

The TZ Archiver CLI follows a modular architecture with clear separation of concerns:

```
src/
├── __init__.py              # Package metadata
├── main.py                  # CLI entry point and orchestration
├── config.py                # Centralized configuration management
├── state_manager.py         # Persistent state handling
├── archiver.py              # Wayback Machine archiving logic
├── processor.py             # Token processing and business logic
├── utils/                   # Utility modules
│   ├── __init__.py          # Utils package exports
│   ├── logger.py            # Advanced logging system
│   └── tzkt.py              # TzKT API client
└── data/                    # Runtime data storage
    ├── processed_cids.json  # Successfully processed CIDs
    └── errors_cids.json     # Failed archiving attempts
```

## Module Responsibilities

### Core Modules

- **`main.py`**: CLI interface, argument parsing, and application orchestration
- **`config.py`**: Centralized configuration constants and environment management
- **`state_manager.py`**: Persistent storage of application state (processed/error CIDs)
- **`archiver.py`**: Wayback Machine integration with concurrency control
- **`processor.py`**: Business logic for token processing and workflow coordination

### Utility Modules

- **`utils/logger.py`**: Advanced logging with colored output and timestamps
- **`utils/tzkt.py`**: Typed TzKT API client for Tezos blockchain data

## Design Patterns Used

### 1. **Dependency Injection**
Components are injected rather than created internally, improving testability and modularity.

### 2. **Strategy Pattern**
Different processing strategies (WalletProcessor, SpiderProcessor) share a common interface.

### 3. **Observer Pattern**
Callback-based architecture for asynchronous archiving operations.

### 4. **Single Responsibility Principle**
Each module has a single, well-defined responsibility.

### 5. **Configuration Object Pattern**
Centralized configuration management through the Config class.

## Data Flow

```
CLI Args → Validation → Component Setup → State Loading → Processing → Archiving → State Saving
```

1. **Input Processing**: CLI arguments are parsed and validated
2. **Component Initialization**: All required components are created with proper dependencies
3. **State Management**: Previous session state is loaded from disk
4. **Token Discovery**: Tokens are fetched from TzKT API (wallet-specific or random)
5. **Filtering**: IPFS artifacts are extracted and deduplicated
6. **Archiving**: URLs are submitted to Wayback Machine with concurrency control
7. **State Persistence**: Results are immediately saved to disk

## Error Handling Strategy

### 1. **Graceful Degradation**
- Network failures don't crash the application
- Malformed data is skipped with logging
- State is preserved even on unexpected termination

### 2. **Immediate Persistence**
- CIDs are saved immediately upon processing
- No data loss on interruption
- Resume capability built-in

### 3. **Comprehensive Logging**
- All operations are logged with appropriate levels
- Colored output for better debugging
- Timestamps for audit trails

## Concurrency Management

### Rate Limiting
- Respects Wayback Machine's 12 captures/minute limit
- Configurable concurrent processing slots
- Automatic backoff on capacity constraints

### Thread Safety
- State manager handles concurrent access to shared data
- Atomic operations for CID persistence
- Clean resource management

## Testing Strategy

### Unit Tests (Recommended)
```python
# Example test structure
tests/
├── test_config.py           # Configuration validation
├── test_state_manager.py    # State persistence logic
├── test_archiver.py         # Archiving functionality
├── test_processor.py        # Business logic
└── test_utils/
    ├── test_logger.py       # Logging functionality
    └── test_tzkt.py         # API client
```

### Integration Tests
- End-to-end workflow testing
- API integration validation
- State persistence verification

## Performance Considerations

### Memory Management
- Streaming processing for large datasets
- Efficient set operations for deduplication
- Minimal memory footprint for state storage

### Network Optimization
- Built-in delays to respect API rate limits
- Concurrent processing with configurable limits
- Automatic retry mechanisms for transient failures

### Disk I/O
- Immediate persistence of critical state
- JSON format for human-readable storage
- Atomic write operations to prevent corruption

## Security Considerations

### Credential Management
- Environment variable-based configuration
- No hardcoded secrets
- Clear error messages for missing credentials

### Data Validation
- Input sanitization for wallet addresses
- Type checking for API responses
- Safe file operations with error handling

## Extensibility Points

### Adding New Token Sources
Implement the processor interface to add new token discovery methods.

### Custom Archiving Targets
Extend the archiver module to support additional preservation services.

### Enhanced Filtering
Add custom filters in the processor module for specific token criteria.

### Monitoring Integration
Add hooks in the logger module for external monitoring systems.

## Development Workflow

### Code Style
- Type hints throughout
- Comprehensive docstrings
- Clear error messages
- Consistent naming conventions

### Version Control
- Feature branches for new functionality
- Conventional commit messages
- Semantic versioning

### Deployment
- Environment-specific configuration
- Docker containerization ready
- CI/CD pipeline compatible
