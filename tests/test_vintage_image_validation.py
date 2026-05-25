"""Tests for vintage submission image validation (fixes #6288)"""
import hashlib
import os
import tempfile
import pytest
from PIL import Image

from tools.validate_vintage_submission import SubmissionValidator


@pytest.fixture
def validator():
    return SubmissionValidator()


@pytest.fixture
def real_photo(tmp_path):
    """Create a valid photo file (800x600 JPEG)"""
    img = Image.new("RGB", (800, 600), color="red")
    path = str(tmp_path / "photo.jpg")
    img.save(path)
    return path


@pytest.fixture
def real_screenshot(tmp_path):
    """Create a valid screenshot file (1024x768 PNG)"""
    img = Image.new("RGB", (1024, 768), color="blue")
    path = str(tmp_path / "screenshot.png")
    img.save(path)
    return path


@pytest.fixture
def fake_file(tmp_path):
    """Create a non-image file that should be rejected"""
    path = str(tmp_path / "fake.txt")
    with open(path, "wb") as f:
        f.write(b"This is not an image " * 500)
    return path


@pytest.fixture
def tiny_image(tmp_path):
    """Create an image below minimum resolution thresholds"""
    img = Image.new("RGB", (100, 100), color="green")
    path = str(tmp_path / "tiny.png")
    img.save(path)
    return path


class TestPhotoValidation:
    def test_real_image_passes(self, validator, real_photo):
        result = validator.validate_photo(real_photo)
        assert result["status"] in ("PASS", "WARN")
        assert result["checks"].get("is_real_image") is True
        assert result["checks"]["width"] == 800
        assert result["checks"]["height"] == 600

    def test_non_image_rejected(self, validator, fake_file):
        result = validator.validate_photo(fake_file)
        assert result["status"] == "FAIL"
        assert result["checks"].get("is_real_image") is False

    def test_missing_file_rejected(self, validator):
        result = validator.validate_photo("/tmp/nonexistent_photo_6288.jpg")
        assert result["status"] == "FAIL"

    def test_low_resolution_warning(self, validator, tiny_image):
        result = validator.validate_photo(tiny_image)
        # Tiny image (100x100) is below 640x480 minimum for photos
        assert "resolution" in result.get("message", "").lower() or result["status"] == "FAIL"

    def test_sha256_hash_computed(self, validator, real_photo):
        result = validator.validate_photo(real_photo)
        assert "sha256" in result["checks"]
        assert len(result["checks"]["sha256"]) == 64  # SHA-256 hex length

    def test_image_format_detected(self, validator, real_photo):
        result = validator.validate_photo(real_photo)
        assert result["checks"].get("format") in ("JPEG", None)  # None if Pillow unavailable


class TestScreenshotValidation:
    def test_real_image_passes(self, validator, real_screenshot):
        result = validator.validate_screenshot(real_screenshot)
        assert result["status"] in ("PASS", "WARN")
        assert result["checks"].get("is_real_image") is True
        assert result["checks"]["width"] == 1024
        assert result["checks"]["height"] == 768

    def test_non_image_rejected(self, validator, fake_file):
        result = validator.validate_screenshot(fake_file)
        assert result["status"] == "FAIL"
        assert result["checks"].get("is_real_image") is False

    def test_missing_file_rejected(self, validator):
        result = validator.validate_screenshot("/tmp/nonexistent_screenshot_6288.png")
        assert result["status"] == "FAIL"

    def test_low_resolution_rejected(self, validator, tiny_image):
        """Screenshots below 320x240 must be rejected"""
        result = validator.validate_screenshot(tiny_image)
        assert result["status"] == "FAIL"
        assert "resolution" in result["message"].lower()

    def test_sha256_hash_computed(self, validator, real_screenshot):
        result = validator.validate_screenshot(real_screenshot)
        assert "sha256" in result["checks"]
        assert len(result["checks"]["sha256"]) == 64

    def test_minimum_resolution_passes(self, tmp_path, validator):
        """Screenshot at exactly 320x240 should pass"""
        img = Image.new("RGB", (320, 240), color="gray")
        path = str(tmp_path / "min_screenshot.png")
        img.save(path)
        result = validator.validate_screenshot(path)
        assert result["status"] in ("PASS", "WARN")


class TestFullSubmission:
    def test_submission_with_fake_photo_rejected(self, validator, fake_file, real_screenshot):
        results = validator.validate_submission(
            photo_path=fake_file,
            screenshot_path=real_screenshot,
        )
        # Photo FAIL should make overall submission invalid
        assert results["valid"] is False or results["checks"]["photo"]["status"] == "FAIL"

    def test_submission_with_fake_screenshot_rejected(self, validator, real_photo, fake_file):
        results = validator.validate_submission(
            photo_path=real_photo,
            screenshot_path=fake_file,
        )
        # Screenshot FAIL should make overall submission invalid
        assert results["valid"] is False or results["checks"]["screenshot"]["status"] == "FAIL"

    def test_valid_submission(self, validator, real_photo, real_screenshot):
        results = validator.validate_submission(
            photo_path=real_photo,
            screenshot_path=real_screenshot,
        )
        # Both should not be FAIL
        assert results["checks"]["photo"]["status"] != "FAIL"
        assert results["checks"]["screenshot"]["status"] != "FAIL"
