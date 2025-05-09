"""Tests for the asset management utility functions."""

import hashlib
import io  # Import the io module for BytesIO
import tarfile
import zipfile
from pathlib import Path

import filelock
import pytest

from openmas.assets.exceptions import AssetUnpackError
from openmas.assets.utils import (
    AssetLock,
    asset_lock,
    async_asset_lock,
    calculate_sha256,
    unpack_archive,
    verify_checksum,
)


class TestChecksumUtils:
    """Tests for the checksum utility functions."""

    def test_calculate_sha256(self, tmp_path):
        """Test calculating SHA256 hash."""
        # Create a temporary file with known content
        test_file = tmp_path / "test_file.txt"
        test_content = b"test content for SHA256 calculation"
        test_file.write_bytes(test_content)

        # Calculate expected hash
        expected_hash = hashlib.sha256(test_content).hexdigest()

        # Test the function
        result = calculate_sha256(test_file)
        assert result == expected_hash

    def test_calculate_sha256_nonexistent_file(self):
        """Test calculating SHA256 hash for a nonexistent file."""
        with pytest.raises(FileNotFoundError):
            calculate_sha256(Path("/nonexistent/file"))

    def test_verify_checksum_valid(self, tmp_path):
        """Test verifying a valid checksum."""
        # Create a temporary file with known content
        test_file = tmp_path / "test_file.txt"
        test_content = b"test content for checksum verification"
        test_file.write_bytes(test_content)

        # Calculate expected hash
        expected_hash = hashlib.sha256(test_content).hexdigest()
        expected_checksum = f"sha256:{expected_hash}"

        # Test the function
        assert verify_checksum(test_file, expected_checksum)

    def test_verify_checksum_invalid(self, tmp_path):
        """Test verifying an invalid checksum."""
        # Create a temporary file with known content
        test_file = tmp_path / "test_file.txt"
        test_content = b"test content for checksum verification"
        test_file.write_bytes(test_content)

        # Use a different hash
        invalid_checksum = "sha256:" + "0" * 64

        # Test the function
        assert not verify_checksum(test_file, invalid_checksum)

    def test_verify_checksum_invalid_format(self, tmp_path):
        """Test verifying a checksum with invalid format."""
        # Create a temporary file
        test_file = tmp_path / "test_file.txt"
        test_file.write_bytes(b"test")

        # Test with invalid format
        with pytest.raises(ValueError):
            verify_checksum(test_file, "md5:abcdef")

        # Test with invalid hash length
        with pytest.raises(ValueError):
            verify_checksum(test_file, "sha256:abc")


class TestUnpackUtils:
    """Tests for the unpacking utility functions."""

    def test_unpack_zip(self, tmp_path):
        """Test unpacking a ZIP archive."""
        # Create a temporary ZIP file
        archive_path = tmp_path / "test.zip"
        target_dir = tmp_path / "extracted"
        target_dir.mkdir()

        # Create content for the ZIP
        with zipfile.ZipFile(archive_path, "w") as zip_file:
            zip_file.writestr("test.txt", "test content")
            zip_file.writestr("subdir/nested.txt", "nested content")

        # Unpack the archive
        unpack_archive(archive_path, target_dir, "zip")

        # Verify the files were extracted
        assert (target_dir / "test.txt").exists()
        assert (target_dir / "subdir" / "nested.txt").exists()
        assert (target_dir / "test.txt").read_text() == "test content"
        assert (target_dir / "subdir" / "nested.txt").read_text() == "nested content"

    def test_unpack_tar(self, tmp_path):
        """Test unpacking a TAR archive."""
        # Create a temporary TAR file
        archive_path = tmp_path / "test.tar"
        target_dir = tmp_path / "extracted"
        target_dir.mkdir()

        # Create content for the TAR
        with tarfile.open(archive_path, "w") as tar_file:
            # Add a file
            test_file = tmp_path / "test.txt"
            test_file.write_text("test content")
            tar_file.add(test_file, arcname="test.txt")

            # Add a subdirectory with a file
            subdir = tmp_path / "subdir"
            subdir.mkdir()
            nested_file = subdir / "nested.txt"
            nested_file.write_text("nested content")
            tar_file.add(subdir, arcname="subdir")

        # Unpack the archive
        unpack_archive(archive_path, target_dir, "tar")

        # Verify the files were extracted
        assert (target_dir / "test.txt").exists()
        assert (target_dir / "subdir" / "nested.txt").exists()
        assert (target_dir / "test.txt").read_text() == "test content"
        assert (target_dir / "subdir" / "nested.txt").read_text() == "nested content"

    def test_unpack_unsupported_format(self, tmp_path):
        """Test unpacking with an unsupported format."""
        # Create a temporary file
        archive_path = tmp_path / "test.xyz"
        archive_path.write_text("not an archive")
        target_dir = tmp_path / "extracted"
        target_dir.mkdir()

        # Test with unsupported format
        with pytest.raises(AssetUnpackError, match="Unsupported archive format: unsupported"):
            unpack_archive(archive_path, target_dir, "unsupported")

    def test_unpack_path_traversal_protection(self, tmp_path):
        """Test protection against path traversal in TAR archives."""
        # Create a temporary TAR file with a path traversal attempt
        archive_path = tmp_path / "malicious.tar"
        target_dir = tmp_path / "extracted"
        target_dir.mkdir()

        # Create a file that will attempt path traversal
        with tarfile.open(archive_path, "w") as tar_file:
            info = tarfile.TarInfo("../outside.txt")
            info.size = len(b"malicious content")
            tar_file.addfile(info, fileobj=io.BytesIO(b"malicious content"))

        # Unpack the archive - should filter out the malicious file
        unpack_archive(archive_path, target_dir, "tar")

        # Verify the path traversal was prevented (file should not exist)
        assert not (tmp_path / "outside.txt").exists()


class TestLockUtils:
    """Tests for the locking utility functions."""

    def test_asset_lock_class(self, tmp_path):
        """Test the AssetLock class."""
        lock_path = tmp_path / "test.lock"

        # Test basic lock acquisition and release
        with AssetLock(lock_path) as lock:
            assert lock.lock.is_locked
            # The lock file should exist
            assert lock_path.with_suffix(".lock").exists()

        # After exiting the context, the lock should be released
        assert not lock.lock.is_locked

    def test_asset_lock_context_manager(self, tmp_path):
        """Test the asset_lock context manager."""
        lock_path = tmp_path / "test.lock"

        # Test basic lock acquisition and release
        with asset_lock(lock_path):
            # Create a FileLock object to check if the file is locked
            check_lock = filelock.FileLock(str(lock_path))
            # Should not be able to acquire the lock
            with pytest.raises(filelock.Timeout):
                check_lock.acquire(timeout=0.1)

        # After exiting the context, the lock should be released
        check_lock = filelock.FileLock(str(lock_path))
        # Should be able to acquire the lock now
        check_lock.acquire(timeout=0.1)
        check_lock.release()

    @pytest.mark.asyncio
    async def test_async_asset_lock(self, tmp_path):
        """Test the async_asset_lock context manager."""
        lock_path = tmp_path / "test.lock"

        # Test basic lock acquisition and release
        async with async_asset_lock(lock_path):
            # Create a FileLock object to check if the file is locked
            check_lock = filelock.FileLock(str(lock_path))
            # Should not be able to acquire the lock
            with pytest.raises(filelock.Timeout):
                check_lock.acquire(timeout=0.1)

        # After exiting the context, the lock should be released
        check_lock = filelock.FileLock(str(lock_path))
        # Should be able to acquire the lock now
        check_lock.acquire(timeout=0.1)
        check_lock.release()

    def test_lock_timeout(self, tmp_path):
        """Test timeout behavior of lock acquisition."""
        lock_path = tmp_path / "test.lock"

        # Acquire a lock with a separate FileLock
        external_lock = filelock.FileLock(str(lock_path))
        external_lock.acquire()

        try:
            # Try to acquire the same lock with a timeout of 0.1 seconds
            with pytest.raises(filelock.Timeout):
                with AssetLock(lock_path, timeout=0.1):
                    pass
        finally:
            # Release the external lock
            external_lock.release()
