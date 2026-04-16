from __future__ import annotations

import logging
from pathlib import Path
import shutil
import tarfile
import tempfile
from urllib.parse import urlparse
from urllib.request import urlretrieve
import zipfile

logger = logging.getLogger(__name__)


def ensure_pdf_assets(
    *,
    pdf_dir: Path,
    archive_url: str,
    archive_path: Path,
    download_enabled: bool,
) -> None:
    """Ensure recommendation PDFs are present, downloading and unpacking an archive if needed."""

    pdf_dir.mkdir(parents=True, exist_ok=True)
    if _has_pdf_files(pdf_dir):
        logger.info("Clinical recommendation PDFs already exist in %s", pdf_dir)
        return

    if not download_enabled:
        raise RuntimeError(f"Clinical recommendations PDF directory is empty: {pdf_dir}")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if not archive_path.is_file():
        logger.info("Downloading clinical recommendation PDF archive from %s", archive_url)
        _download_archive(archive_url=archive_url, destination=archive_path)
    else:
        logger.info("Using existing clinical recommendation PDF archive at %s", archive_path)

    extracted_count = _extract_pdf_archive(archive_path=archive_path, pdf_dir=pdf_dir)
    if extracted_count == 0:
        raise RuntimeError(f"No PDF files were found in clinical recommendations archive: {archive_path}")
    logger.info("Extracted %s clinical recommendation PDFs into %s", extracted_count, pdf_dir)


def _has_pdf_files(pdf_dir: Path) -> bool:
    return any(path.is_file() for path in pdf_dir.glob("*.pdf"))


def _download_archive(*, archive_url: str, destination: Path) -> None:
    tmp_destination = destination.with_suffix(destination.suffix + ".tmp")
    if tmp_destination.exists():
        tmp_destination.unlink()

    try:
        if "drive.google.com" in urlparse(archive_url).netloc:
            _download_google_drive_archive(archive_url=archive_url, destination=tmp_destination)
        else:
            urlretrieve(archive_url, tmp_destination)
        tmp_destination.replace(destination)
    finally:
        if tmp_destination.exists():
            tmp_destination.unlink()


def _download_google_drive_archive(*, archive_url: str, destination: Path) -> None:
    try:
        import gdown
    except ImportError as exc:
        raise RuntimeError("Install gdown to download the clinical recommendations archive from Google Drive.") from exc

    downloaded_path = gdown.download(url=archive_url, output=str(destination), quiet=False, fuzzy=True)
    if not downloaded_path:
        raise RuntimeError(f"Failed to download Google Drive archive: {archive_url}")


def _extract_pdf_archive(*, archive_path: Path, pdf_dir: Path) -> int:
    with tempfile.TemporaryDirectory(prefix="clinical_recommendations_", dir=archive_path.parent) as temp_name:
        temp_dir = Path(temp_name)
        if zipfile.is_zipfile(archive_path):
            _extract_zip_safely(archive_path=archive_path, destination=temp_dir)
        elif tarfile.is_tarfile(archive_path):
            _extract_tar_safely(archive_path=archive_path, destination=temp_dir)
        else:
            shutil.unpack_archive(str(archive_path), str(temp_dir))

        count = 0
        for source_pdf in temp_dir.rglob("*.pdf"):
            destination_pdf = pdf_dir / source_pdf.name
            shutil.move(str(source_pdf), destination_pdf)
            count += 1
        return count


def _extract_zip_safely(*, archive_path: Path, destination: Path) -> None:
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if target != destination_root and destination_root not in target.parents:
                raise RuntimeError(f"Unsafe archive member path: {member.filename}")
        archive.extractall(destination)


def _extract_tar_safely(*, archive_path: Path, destination: Path) -> None:
    destination_root = destination.resolve()
    with tarfile.open(archive_path) as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise RuntimeError(f"Unsafe archive link member: {member.name}")
            target = (destination / member.name).resolve()
            if target != destination_root and destination_root not in target.parents:
                raise RuntimeError(f"Unsafe archive member path: {member.name}")
        archive.extractall(destination)
