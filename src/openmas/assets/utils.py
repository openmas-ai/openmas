"""Utilities for asset management."""

import hashlib
import tarfile
import zipfile
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional

import filelock

from openmas.assets.exceptions import AssetUnpackError, AssetVerificationError
from openmas.logging import get_logger

logger = get_logger(__name__)

# Default chunk size for file reading (16 MB)
DEFAULT_CHUNK_SIZE = 16 * 1024 * 1024


def calculate_sha256(file_path: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """Calculate the SHA256 hash of a file.

    Args:
        file_path: Path to the file
        chunk_size: Size of chunks to read at a time (bytes)

    Returns:
        The SHA256 hash as a hexadecimal string

    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If the file cannot be read
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256 = hashlib.sha256()
    total_size = file_path.stat().st_size
    processed = 0

    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
            processed += len(chunk)
            # Log progress for large files (>100MB)
            if total_size > 100 * 1024 * 1024 and processed % (50 * 1024 * 1024) < chunk_size:
                logger.debug(f"Checksumming progress: {processed / total_size:.1%}")

    return sha256.hexdigest()


def verify_checksum(file_path: Path, expected_checksum: str) -> bool:
    """Verify a file's checksum against an expected value.

    Args:
        file_path: Path to the file
        expected_checksum: Expected checksum in format "sha256:<hex_digest>"

    Returns:
        True if the checksum matches, False otherwise

    Raises:
        ValueError: If the checksum format is invalid
        FileNotFoundError: If the file does not exist
        AssetVerificationError: If the verification fails for other reasons
    """
    if not expected_checksum.startswith("sha256:"):
        raise ValueError("Unsupported checksum format. Only sha256:<hex_digest> is supported.")

    expected_digest = expected_checksum[7:]  # Remove "sha256:" prefix

    if len(expected_digest) != 64 or not all(c in "0123456789abcdef" for c in expected_digest.lower()):
        raise ValueError("Invalid SHA256 digest format. Expected 64 hexadecimal characters.")

    try:
        actual_digest = calculate_sha256(file_path)
        return actual_digest.lower() == expected_digest.lower()
    except (FileNotFoundError, PermissionError) as e:
        raise e
    except Exception as e:
        raise AssetVerificationError(f"Error verifying checksum: {str(e)}") from e


def unpack_archive(archive_path: Path, target_dir: Path, format: str, destination_is_file: bool = False) -> Path:
    """Unpack an archive file.

    Args:
        archive_path: Path to the archive file
        target_dir: Directory to extract the archive to
        format: Format of the archive ("zip", "tar", "tar.gz", "tar.bz2")
        destination_is_file: If True, expects the archive to contain a single file and returns the path to it

    Returns:
        Path to the unpacked directory or file (if destination_is_file is True)

    Raises:
        FileNotFoundError: If the archive file does not exist
        ValueError: If the format is unsupported
        AssetUnpackError: If the unpacking fails
    """
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    # Ensure target directory exists
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Unpacking {archive_path} to {target_dir} (format: {format})")

    try:
        if format == "zip":
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(target_dir)

                # If destination_is_file is True, find the content file
                if destination_is_file:
                    # Get list of files (not directories) in the archive
                    files = [f for f in zip_ref.namelist() if not f.endswith("/")]

                    if not files:
                        raise AssetUnpackError("No files found in ZIP archive")

                    # Check if there's only one file or one main file (ignoring metadata)
                    content_files = [f for f in files if not f.startswith(".") and not f.startswith("__MACOSX/")]

                    if len(content_files) == 1:
                        # Return the path to the single file
                        return target_dir / content_files[0]
                    else:
                        # If multiple files, find a possible primary file or the first one
                        file_path = None
                        # Check for a common root file
                        root_files = [f for f in content_files if "/" not in f]
                        if root_files:
                            file_path = target_dir / root_files[0]
                        else:
                            file_path = target_dir / content_files[0]

                        logger.warning(
                            f"Multiple files found in archive when destination_is_file=True. "
                            f"Using {file_path.relative_to(target_dir)} as the primary file."
                        )
                        return file_path

                return target_dir

        elif format in ("tar", "tar.gz", "tar.bz2"):
            mode = {
                "tar": "r",
                "tar.gz": "r:gz",
                "tar.bz2": "r:bz2",
            }[format]
            with tarfile.open(str(archive_path), mode) as tar_ref:  # type: ignore
                # Check for path traversal vulnerabilities (CVE-2007-4559)
                def is_safe(member: tarfile.TarInfo) -> bool:
                    # Avoid path traversal using extracted paths
                    return not member.name.startswith("/") and ".." not in member.name.split("/")

                # Get safe members
                members = [member for member in tar_ref.getmembers() if is_safe(member)]
                tar_ref.extractall(target_dir, members=members)

                # If destination_is_file is True, find the content file
                if destination_is_file:
                    # Get list of files (not directories) in the archive
                    files = [m.name for m in members if m.isfile()]

                    if not files:
                        raise AssetUnpackError("No files found in TAR archive")

                    # Check if there's only one file or one main file (ignoring metadata)
                    content_files = [f for f in files if not f.startswith(".") and not f.startswith("__MACOSX/")]

                    if len(content_files) == 1:
                        # Return the path to the single file
                        return target_dir / content_files[0]
                    else:
                        # If multiple files, find a possible primary file or the first one
                        file_path = None
                        # Check for a common root file
                        root_files = [f for f in content_files if "/" not in f]
                        if root_files:
                            file_path = target_dir / root_files[0]
                        else:
                            file_path = target_dir / content_files[0]

                        logger.warning(
                            f"Multiple files found in archive when destination_is_file=True. "
                            f"Using {file_path.relative_to(target_dir)} as the primary file."
                        )
                        return file_path

                return target_dir
        else:
            raise ValueError(f"Unsupported archive format: {format}")

        logger.info(f"Successfully unpacked {archive_path}")
        return target_dir
    except (zipfile.BadZipFile, tarfile.TarError) as e:
        raise AssetUnpackError(f"Error unpacking archive: {str(e)}") from e
    except Exception as e:
        raise AssetUnpackError(f"Unexpected error unpacking archive: {str(e)}") from e


class AssetLock:
    """A context manager for acquiring locks on assets during operations."""

    def __init__(self, lock_path: Path, timeout: Optional[float] = None):
        """Initialize the lock.

        Args:
            lock_path: Path to the lock file
            timeout: Maximum time to wait for the lock (seconds), or None to wait indefinitely
        """
        self.lock_path = lock_path
        self.timeout = timeout
        self.lock = filelock.FileLock(str(lock_path), timeout=timeout or 0)

    def __enter__(self) -> "AssetLock":
        """Acquire the lock."""
        logger.debug(f"Acquiring lock: {self.lock_path}")
        self.lock.acquire()
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[object]) -> None:
        """Release the lock."""
        logger.debug(f"Releasing lock: {self.lock_path}")
        self.lock.release()

    async def __aenter__(self) -> "AssetLock":
        """Acquire the lock asynchronously.

        Note: Since filelock doesn't support async operations directly,
        we use it in a blocking way, but provide the async interface
        for consistent usage in async code.
        """
        logger.debug(f"Acquiring lock asynchronously: {self.lock_path}")
        self.lock.acquire()
        return self

    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[object]) -> None:
        """Release the lock asynchronously."""
        logger.debug(f"Releasing lock asynchronously: {self.lock_path}")
        self.lock.release()


@contextmanager
def asset_lock(lock_path: Path, timeout: Optional[float] = None) -> Generator[None, None, None]:
    """Context manager for acquiring an asset lock.

    This is a convenience wrapper around AssetLock class.

    Args:
        lock_path: Path to the lock file
        timeout: Maximum time to wait for the lock (seconds), or None to wait indefinitely

    Yields:
        None

    Example:
        ```python
        with asset_lock(lock_path):
            # Perform atomic operations
        ```
    """
    with AssetLock(lock_path, timeout) as _:
        yield


@asynccontextmanager
async def async_asset_lock(lock_path: Path, timeout: Optional[float] = None) -> AsyncGenerator[None, None]:
    """Async context manager for acquiring an asset lock.

    This is a convenience wrapper around AssetLock class for async usage.

    Args:
        lock_path: Path to the lock file
        timeout: Maximum time to wait for the lock (seconds), or None to wait indefinitely

    Yields:
        None

    Example:
        ```python
        async with async_asset_lock(lock_path):
            # Perform async atomic operations
        ```
    """
    lock = AssetLock(lock_path, timeout)
    try:
        await lock.__aenter__()
        yield
    finally:
        await lock.__aexit__(None, None, None)
