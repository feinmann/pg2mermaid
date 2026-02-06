"""Export Mermaid diagrams to SVG, PNG, and PDF formats."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from enum import Enum
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ExportFormat(Enum):
    """Supported export formats."""

    SVG = "svg"
    PNG = "png"
    PDF = "pdf"


class ExportMethod(Enum):
    """Export method to use."""

    AUTO = "auto"  # Try local first, fall back to online
    LOCAL = "local"  # Use mermaid-cli (mmdc)
    ONLINE = "online"  # Use kroki.io API


class ExportError(Exception):
    """Error during export."""

    pass


def export_diagram(
    mermaid_code: str,
    output_path: str | Path,
    format: ExportFormat = ExportFormat.SVG,
    method: ExportMethod = ExportMethod.AUTO,
    background: str = "white",
    theme: str = "default",
    scale: int = 2,
    timeout: int = 30,
) -> Path:
    """
    Export a Mermaid diagram to an image file.

    Args:
        mermaid_code: The Mermaid diagram code.
        output_path: Path to save the output file.
        format: Output format (SVG, PNG, PDF).
        method: Export method (AUTO, LOCAL, ONLINE).
        background: Background color (for PNG).
        theme: Mermaid theme (default, dark, forest, neutral).
        scale: Scale factor for PNG output.
        timeout: Timeout in seconds for online requests.

    Returns:
        Path to the created file.

    Raises:
        ExportError: If export fails.
    """
    output_path = Path(output_path)

    # Ensure correct extension
    if not output_path.suffix:
        output_path = output_path.with_suffix(f".{format.value}")

    if method == ExportMethod.AUTO:
        # Try local first, fall back to online
        if _mmdc_available():
            return _export_local(
                mermaid_code, output_path, format, background, theme, scale
            )
        else:
            return _export_online(mermaid_code, output_path, format, timeout)
    elif method == ExportMethod.LOCAL:
        if not _mmdc_available():
            raise ExportError(
                "mermaid-cli (mmdc) not found. Install with: npm install -g @mermaid-js/mermaid-cli"
            )
        return _export_local(
            mermaid_code, output_path, format, background, theme, scale
        )
    else:  # ONLINE
        return _export_online(mermaid_code, output_path, format, timeout)


def _mmdc_available() -> bool:
    """Check if mermaid-cli is installed."""
    return shutil.which("mmdc") is not None


def _export_local(
    mermaid_code: str,
    output_path: Path,
    format: ExportFormat,
    background: str,
    theme: str,
    scale: int,
) -> Path:
    """Export using local mermaid-cli."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".mmd", delete=False
    ) as tmp_input:
        tmp_input.write(mermaid_code)
        tmp_input_path = tmp_input.name

    try:
        cmd = [
            "mmdc",
            "-i",
            tmp_input_path,
            "-o",
            str(output_path),
            "-b",
            background,
            "-t",
            theme,
        ]

        if format == ExportFormat.PNG:
            cmd.extend(["-s", str(scale)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise ExportError(f"mermaid-cli failed: {error_msg}")

        if not output_path.exists():
            raise ExportError(f"Output file was not created: {output_path}")

        return output_path

    except subprocess.TimeoutExpired:
        raise ExportError("mermaid-cli timed out")
    except FileNotFoundError:
        raise ExportError("mermaid-cli (mmdc) not found in PATH")
    finally:
        Path(tmp_input_path).unlink(missing_ok=True)


def _export_online(
    mermaid_code: str,
    output_path: Path,
    format: ExportFormat,
    timeout: int,
) -> Path:
    """Export using kroki.io API."""
    url = f"https://kroki.io/mermaid/{format.value}"

    try:
        # Use POST with plain text body
        data = mermaid_code.encode("utf-8")
        request = Request(url, data=data, method="POST")
        request.add_header("Content-Type", "text/plain")
        request.add_header("Accept", f"image/{format.value}")
        request.add_header("User-Agent", "pg2mermaid/0.1.0")

        with urlopen(request, timeout=timeout) as response:
            content = response.read()

        output_path.write_bytes(content)
        return output_path

    except HTTPError as e:
        if e.code == 400:
            error_body = e.read().decode()
            raise ExportError(f"Invalid Mermaid syntax: {error_body}")
        raise ExportError(f"Kroki API error: HTTP {e.code}")
    except URLError as e:
        raise ExportError(f"Network error: {e.reason}")
    except TimeoutError:
        raise ExportError("Request to kroki.io timed out")


def get_available_methods() -> list[ExportMethod]:
    """Get list of available export methods."""
    methods = [ExportMethod.ONLINE]  # Always available
    if _mmdc_available():
        methods.insert(0, ExportMethod.LOCAL)
    return methods


def check_dependencies() -> dict[str, bool]:
    """Check which export dependencies are available."""
    return {
        "mmdc (mermaid-cli)": _mmdc_available(),
        "kroki.io (online)": True,  # Always available if internet works
    }
