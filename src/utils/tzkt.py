"""
TzKT API Client for Tezos Blockchain Data

A typed Python client for the TzKT API that provides access to Tezos token data.
Includes comprehensive dataclasses for type safety and parsing utilities.

Author: Refactored from ChatGPT generated code
License: MIT
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional
import requests
import random


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class Dimensions:
    """Media dimensions with unit and value."""

    unit: Optional[str] = None
    value: Optional[str] = None


@dataclass
class DataRate:
    """Data rate specification with unit and value."""

    unit: Optional[str] = None
    value: Optional[str] = None


@dataclass
class Format:
    """Media format specification."""

    uri: Optional[str] = None
    fileName: Optional[str] = None
    fileSize: Optional[str] = None
    mimeType: Optional[str] = None
    dimensions: Optional[Dimensions] = None
    dataRate: Optional[DataRate] = None
    duration: Optional[str] = None


@dataclass
class Gpu:
    """GPU hardware specification (placeholder)."""

    pass


@dataclass
class Hardware:
    """Hardware specification."""

    gpu: Optional[Gpu] = None


@dataclass
class Viewport:
    """Viewport dimensions and scale."""

    width: Optional[str] = None
    height: Optional[str] = None
    deviceScaleFactor: Optional[str] = None


@dataclass
class Resolution:
    """Screen resolution."""

    x: Optional[str] = None
    y: Optional[str] = None


@dataclass
class Software:
    """Software specification with version and display settings."""

    name: Optional[str] = None
    version: Optional[str] = None
    viewport: Optional[Viewport] = None
    resolution: Optional[Resolution] = None


@dataclass
class Preservation:
    """Preservation metadata for hardware and software."""

    hardware: Optional[List[Hardware]] = None
    software: Optional[List[Software]] = None


@dataclass
class Accessibility:
    """Accessibility information including hazards."""

    hazards: Optional[List[str]] = None


@dataclass
class Royalties:
    """Royalty information with shares and decimals."""

    shares: Optional[Dict[str, str]] = None
    decimals: Optional[str] = None


@dataclass
class Metadata:
    """Comprehensive token metadata."""

    date: Optional[str] = None
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    image: Optional[str] = None
    minter: Optional[str] = None
    rights: Optional[str] = None
    symbol: Optional[str] = None
    formats: Optional[List[Format]] = None
    creators: Optional[List[str]] = None
    decimals: Optional[str] = None
    royalties: Optional[Royalties] = None
    attributes: Any = None
    displayUri: Optional[str] = None
    artifactUri: Optional[str] = None
    description: Optional[str] = None
    mintingTool: Optional[str] = None
    thumbnailUri: Optional[str] = None
    authors: Optional[List[str]] = None
    mimeType: Optional[str] = None
    authoraddress: Optional[List[str]] = None
    artists: Optional[List[str]] = None
    minterkey: Optional[str] = None
    isBooleanAmount: Optional[bool] = None
    shouldPreferSymbol: Optional[bool] = None
    language: Optional[str] = None
    accessibility: Optional[Accessibility] = None
    preservation: Optional[Preservation] = None
    editions: Optional[str] = None
    mintingToolVersion: Optional[str] = None
    contentRating: Optional[str] = None
    version: Optional[str] = None
    generatorUri: Optional[str] = None
    iterationHash: Optional[str] = None
    snippetVersion: Optional[str] = None
    authenticityHash: Optional[str] = None


@dataclass
class Contract:
    """Contract information with alias and address."""

    alias: Optional[str] = None
    address: Optional[str] = None


@dataclass
class FirstMinter:
    """First minter information with alias and address."""

    alias: Optional[str] = None
    address: Optional[str] = None


@dataclass
class Token:
    """Complete token information from TzKT API."""

    id: Optional[int] = None
    contract: Optional[Contract] = None
    tokenId: Optional[str] = None
    standard: Optional[str] = None
    firstMinter: Optional[FirstMinter] = None
    firstLevel: Optional[int] = None
    firstTime: Optional[str] = None
    lastLevel: Optional[int] = None
    lastTime: Optional[str] = None
    transfersCount: Optional[int] = None
    balancesCount: Optional[int] = None
    holdersCount: Optional[int] = None
    totalMinted: Optional[str] = None
    totalBurned: Optional[str] = None
    totalSupply: Optional[str] = None
    metadata: Optional[Metadata] = None


# Type alias for lists of tokens
Tokens = List[Token]


# =============================================================================
# PARSING UTILITIES
# =============================================================================


def _safe_int(value: Any) -> Optional[int]:
    """Safely convert value to integer."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_dimensions(data: Optional[Dict[str, Any]]) -> Optional[Dimensions]:
    """Parse dimensions from API response."""
    return Dimensions(unit=data.get("unit"), value=data.get("value")) if data else None


def _parse_datarate(data: Optional[Dict[str, Any]]) -> Optional[DataRate]:
    """Parse data rate from API response."""
    return DataRate(unit=data.get("unit"), value=data.get("value")) if data else None


def _parse_format(data: Optional[Dict[str, Any]]) -> Optional[Format]:
    """Parse format from API response."""
    if not data:
        return None

    return Format(
        uri=data.get("uri"),
        fileName=data.get("fileName"),
        fileSize=data.get("fileSize"),
        mimeType=data.get("mimeType"),
        dimensions=_parse_dimensions(data.get("dimensions")),
        dataRate=_parse_datarate(data.get("dataRate")),
        duration=data.get("duration"),
    )


def _parse_gpu(data: Any) -> Optional[Gpu]:
    """Parse GPU data (placeholder implementation)."""
    return Gpu() if data is not None else None


def _parse_hardware(data: Optional[Dict[str, Any]]) -> Optional[Hardware]:
    """Parse hardware from API response."""
    return Hardware(gpu=_parse_gpu(data.get("gpu"))) if data else None


def _parse_viewport(data: Optional[Dict[str, Any]]) -> Optional[Viewport]:
    """Parse viewport from API response."""
    if not data:
        return None

    return Viewport(
        width=data.get("width"),
        height=data.get("height"),
        deviceScaleFactor=data.get("deviceScaleFactor"),
    )


def _parse_resolution(data: Optional[Dict[str, Any]]) -> Optional[Resolution]:
    """Parse resolution from API response."""
    return Resolution(x=data.get("x"), y=data.get("y")) if data else None


def _parse_software(data: Optional[Dict[str, Any]]) -> Optional[Software]:
    """Parse software from API response."""
    if not data:
        return None

    return Software(
        name=data.get("name"),
        version=data.get("version"),
        viewport=_parse_viewport(data.get("viewport")),
        resolution=_parse_resolution(data.get("resolution")),
    )


def _parse_preservation(data: Optional[Dict[str, Any]]) -> Optional[Preservation]:
    """Parse preservation metadata from API response."""
    if not data:
        return None

    hardware_list = data.get("hardware")
    software_list = data.get("software")

    parsed_hardware = None
    parsed_software = None

    if hardware_list and isinstance(hardware_list, list):
        parsed_hardware = [_parse_hardware(h) for h in hardware_list if h is not None]

    if software_list and isinstance(software_list, list):
        parsed_software = [_parse_software(s) for s in software_list if s is not None]

    return Preservation(hardware=parsed_hardware, software=parsed_software)


def _parse_accessibility(data: Optional[Dict[str, Any]]) -> Optional[Accessibility]:
    """Parse accessibility from API response."""
    return Accessibility(hazards=data.get("hazards")) if data else None


def _parse_royalties(data: Optional[Dict[str, Any]]) -> Optional[Royalties]:
    """Parse royalties from API response."""
    if not data:
        return None

    return Royalties(shares=data.get("shares"), decimals=data.get("decimals"))


def _parse_metadata(data: Optional[Dict[str, Any]]) -> Optional[Metadata]:
    """Parse comprehensive metadata from API response."""
    if not data:
        return None

    # Parse formats if present
    formats = None
    if data.get("formats") and isinstance(data.get("formats"), list):
        formats = [_parse_format(f) for f in data.get("formats") if f is not None]

    return Metadata(
        date=data.get("date"),
        name=data.get("name"),
        tags=data.get("tags"),
        image=data.get("image"),
        minter=data.get("minter"),
        rights=data.get("rights"),
        symbol=data.get("symbol"),
        formats=formats,
        creators=data.get("creators"),
        decimals=data.get("decimals"),
        royalties=_parse_royalties(data.get("royalties")),
        attributes=data.get("attributes"),
        displayUri=data.get("displayUri"),
        artifactUri=data.get("artifactUri"),
        description=data.get("description"),
        mintingTool=data.get("mintingTool"),
        thumbnailUri=data.get("thumbnailUri"),
        authors=data.get("authors"),
        mimeType=data.get("mimeType"),
        authoraddress=data.get("authoraddress"),
        artists=data.get("artists"),
        minterkey=data.get("minterkey"),
        isBooleanAmount=data.get("isBooleanAmount"),
        shouldPreferSymbol=data.get("shouldPreferSymbol"),
        language=data.get("language"),
        accessibility=_parse_accessibility(data.get("accessibility")),
        preservation=_parse_preservation(data.get("preservation")),
        editions=data.get("editions"),
        mintingToolVersion=data.get("mintingToolVersion"),
        contentRating=data.get("contentRating"),
        version=data.get("version"),
        generatorUri=data.get("generatorUri"),
        iterationHash=data.get("iterationHash"),
        snippetVersion=data.get("snippetVersion"),
        authenticityHash=data.get("authenticityHash"),
    )


def _parse_contract(data: Optional[Dict[str, Any]]) -> Optional[Contract]:
    """Parse contract from API response."""
    return (
        Contract(alias=data.get("alias"), address=data.get("address")) if data else None
    )


def _parse_first_minter(data: Optional[Dict[str, Any]]) -> Optional[FirstMinter]:
    """Parse first minter from API response."""
    return (
        FirstMinter(alias=data.get("alias"), address=data.get("address"))
        if data
        else None
    )


def _parse_token(data: Dict[str, Any]) -> Token:
    """Parse complete token from API response."""
    return Token(
        id=_safe_int(data.get("id")),
        contract=_parse_contract(data.get("contract")),
        tokenId=data.get("tokenId"),
        standard=data.get("standard"),
        firstMinter=_parse_first_minter(data.get("firstMinter")),
        firstLevel=_safe_int(data.get("firstLevel")),
        firstTime=data.get("firstTime"),
        lastLevel=_safe_int(data.get("lastLevel")),
        lastTime=data.get("lastTime"),
        transfersCount=_safe_int(data.get("transfersCount")),
        balancesCount=_safe_int(data.get("balancesCount")),
        holdersCount=_safe_int(data.get("holdersCount")),
        totalMinted=data.get("totalMinted"),
        totalBurned=data.get("totalBurned"),
        totalSupply=data.get("totalSupply"),
        metadata=_parse_metadata(data.get("metadata")),
    )


def _parse_tokens_list(data: Any) -> Optional[Tokens]:
    """Parse list of tokens from API response."""
    if not isinstance(data, list):
        return None

    parsed_tokens: Tokens = []
    for item in data:
        try:
            parsed_tokens.append(_parse_token(item))
        except Exception:
            # Skip malformed items but continue processing
            continue

    return parsed_tokens


# =============================================================================
# HTTP CLIENT
# =============================================================================

# API Configuration
API_MAX = 10_000
HARDCODED_CURRENT_TOKENS_WITH_ARTIFACTS = 8_000_000


def api_call(url: str, timeout: int = 15) -> requests.Response:
    """
    Make HTTP request to TzKT API with rate limiting.

    Args:
        url: API endpoint URL
        timeout: Request timeout in seconds

    Returns:
        HTTP response object
    """
    time.sleep(0.1)  # Basic rate limiting
    return requests.get(url, timeout=timeout)


def _fetch_paginated_tokens(base_url: str, limit: int, offset: int) -> Optional[Tokens]:
    """
    Fetch tokens with automatic pagination handling.

    Args:
        base_url: Base API URL without pagination parameters
        limit: Maximum number of tokens to fetch
        offset: Starting offset

    Returns:
        List of tokens or None on error
    """
    results: List[Token] = []
    current_offset = offset
    remaining = limit

    try:
        while remaining > 0:
            # Calculate batch size (respect API limits)
            batch_limit = min(API_MAX, remaining)

            # Build URL with pagination
            url = f"{base_url}&limit={batch_limit}&offset={current_offset}"

            # Make API call
            resp = api_call(url)
            resp.raise_for_status()
            data = resp.json()

            # Parse response
            tokens = _parse_tokens_list(data)
            if not tokens:
                break

            results.extend(tokens)

            # Check if we got fewer results than requested (end of data)
            if len(data) < batch_limit:
                break

            # Update pagination state
            current_offset += len(data)
            remaining -= len(data)

        return results

    except Exception:
        return None


# =============================================================================
# PUBLIC API FUNCTIONS
# =============================================================================


def balances(holder: str, limit: int, offset: int) -> Optional[Tokens]:
    """
    Fetch token balances for a specific holder.

    Args:
        holder: Tezos address of the token holder
        limit: Maximum number of tokens to fetch
        offset: Starting offset for pagination

    Returns:
        List of tokens or None on error
    """
    base_url = (
        f"https://api.tzkt.io/v1/tokens/balances"
        f"?account={holder}&balance.ne=0&select=token"
    )
    return _fetch_paginated_tokens(base_url, limit, offset)


def mints(
    creator: str, min_timestamp: Optional[str], limit: int, offset: int
) -> Optional[Tokens]:
    """
    Fetch tokens minted by a specific creator.

    Args:
        creator: Tezos address of the creator
        min_timestamp: Minimum timestamp filter (optional)
        limit: Maximum number of tokens to fetch
        offset: Starting offset for pagination

    Returns:
        List of tokens or None on error
    """
    time_filter = f"&firstTime.ge={min_timestamp}" if min_timestamp else ""
    base_url = (
        f"https://api.tzkt.io/v1/tokens"
        f"?firstMinter={creator}{time_filter}&metadata.artifactUri.null=false"
    )
    return _fetch_paginated_tokens(base_url, limit, offset)


def random_tokens(limit: int) -> Optional[Tokens]:
    """
    Fetch random tokens with artifacts.

    Args:
        limit: Maximum number of tokens to fetch

    Returns:
        List of tokens or None on error
    """
    # Generate random starting offset
    random_offset = random.randint(
        0, max(0, HARDCODED_CURRENT_TOKENS_WITH_ARTIFACTS - 1)
    )

    base_url = "https://api.tzkt.io/v1/tokens?metadata.artifactUri.null=false"
    return _fetch_paginated_tokens(base_url, limit, random_offset)


def contract_tokens(contract: str, limit: int, offset: int) -> Optional[Tokens]:
    """
    Fetch tokens from a specific contract.

    Args:
        contract: Contract address
        limit: Maximum number of tokens to fetch
        offset: Starting offset for pagination

    Returns:
        List of tokens or None on error
    """
    base_url = (
        f"https://api.tzkt.io/v1/tokens"
        f"?contract={contract}&metadata.artifactUri.null=false"
    )
    return _fetch_paginated_tokens(base_url, limit, offset)


def token(contract: str, token_id: str) -> Optional[Token]:
    """
    Fetch a specific token by contract and token ID.

    Args:
        contract: Contract address
        token_id: Token ID

    Returns:
        Token object or None if not found/error
    """
    try:
        url = f"https://api.tzkt.io/v1/tokens?contract={contract}&tokenId={token_id}&limit=1"
        resp = api_call(url)
        resp.raise_for_status()
        data = resp.json()

        tokens = _parse_tokens_list(data)
        return tokens[0] if tokens and len(tokens) > 0 else None

    except Exception:
        return None


def block_count() -> Optional[int]:
    """
    Get the current block count from TzKT API.

    Returns:
        Block count as integer or None on error
    """
    try:
        url = "https://api.tzkt.io/v1/blocks/count"
        resp = api_call(url)
        resp.raise_for_status()
        return int(resp.text)

    except Exception:
        return None


def tokens(limit: int, offset: int) -> Optional[Tokens]:
    """
    Fetch tokens using a deterministic offset for systematic coverage.

    This function is used by the spider mode for deterministic token discovery.

    Args:
        limit: Maximum number of tokens to fetch
        offset: Specific offset position in the token space

    Returns:
        List of tokens or None on error
    """
    try:
        base_url = "https://api.tzkt.io/v1/tokens?metadata.artifactUri.null=false"
        return _fetch_paginated_tokens(base_url, limit, offset)

    except Exception:
        return None
