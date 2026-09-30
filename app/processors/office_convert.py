from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SOFFICE_MISSING = (
    "LibreOffice (soffice) is required to ingest legacy .ppt files.\n"
    "Install it (macOS: brew install --cask libreoffice) or convert the file to .pptx first."
)

_MAC_SOFFICE = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


def find_soffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    if Path(_MAC_SOFFICE).exists():
        return _MAC_SOFFICE
    return None


def convert_ppt_to_pptx(source: Path, out_dir: Path, timeout: float = 300.0) -> Path:
    soffice = find_soffice()
    if soffice is None:
        raise RuntimeError(SOFFICE_MISSING)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Copy to an ASCII name so Vietnamese/NFD filenames and spaces cannot break
    # the output-path lookup, and use a private profile so a running
    # LibreOffice instance cannot block the headless conversion.
    staged = out_dir / "source.ppt"
    shutil.copy2(source, staged)
    profile = (out_dir / "lo_profile").resolve()
    cmd = [
        soffice,
        f"-env:UserInstallation={profile.as_uri()}",
        "--headless",
        "--convert-to",
        "pptx",
        "--outdir",
        str(out_dir),
        str(staged),
    ]
    logger.info("Converting %s to pptx with LibreOffice", source.name)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"LibreOffice conversion timed out after {timeout:.0f}s for {source.name}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"LibreOffice conversion failed for {source.name}: {(exc.stderr or '')[-500:]}"
        ) from exc
    target = out_dir / "source.pptx"
    if not target.is_file():
        raise RuntimeError(f"LibreOffice produced no .pptx for {source.name}")
    return target
