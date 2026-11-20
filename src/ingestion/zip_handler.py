
import zipfile
from pathlib import Path, PurePosixPath


class ZipExtractionError(Exception):
    pass


def extract_txt_files(
    zip_path: str | Path,
    output_dir: str | Path,
    max_total_size: int = 100 * 1024 * 1024,
) -> list[Path]:
    """
    Extract TXT files from a ZIP archive.

    Files are saved using their original basenames.
    Path traversal entries are never extracted.
    """

    zip_path = Path(zip_path)
    output_dir = Path(output_dir)

    if not zip_path.exists():
        raise ZipExtractionError(f"ZIP not found: {zip_path}")

    if not zipfile.is_zipfile(zip_path):
        raise ZipExtractionError("Uploaded file is not a valid ZIP.")

    output_dir.mkdir(parents=True, exist_ok=True)

    extracted_files = []
    total_size = 0
    used_names = set()

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:

            for info in archive.infolist():

                if info.is_dir():
                    continue

                original_name = info.filename

                if not original_name.lower().endswith(".txt"):
                    continue

                # Ignore hidden/system files.
                basename = PurePosixPath(original_name).name

                if not basename or basename.startswith("."):
                    continue

                # Prevent duplicate filenames from overwriting files.
                if basename.lower() in used_names:
                    raise ZipExtractionError(
                        f"Duplicate TXT filename: {basename}"
                    )

                used_names.add(basename.lower())

                if info.file_size > max_total_size:
                    raise ZipExtractionError(
                        f"File too large: {basename}"
                    )

                total_size += info.file_size

                if total_size > max_total_size:
                    raise ZipExtractionError(
                        "ZIP exceeds maximum allowed extraction size."
                    )

                destination = output_dir / basename

                # Additional containment check.
                if destination.resolve().parent != output_dir.resolve():
                    raise ZipExtractionError(
                        f"Unsafe extraction path: {original_name}"
                    )

                with archive.open(info, "r") as source:
                    data = source.read(max_total_size + 1)

                if len(data) > max_total_size:
                    raise ZipExtractionError(
                        f"Extracted file exceeds size limit: {basename}"
                    )

                destination.write_bytes(data)
                extracted_files.append(destination)

    except zipfile.BadZipFile as exc:
        raise ZipExtractionError(
            "The uploaded ZIP archive is corrupted."
        ) from exc

    return sorted(
        extracted_files,
        key=lambda path: path.name.lower()
    )
