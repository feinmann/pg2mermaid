"""Export Mermaid diagrams to SVG, PNG, and PDF formats."""

from __future__ import annotations

import json
import re
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
    export_format: ExportFormat = ExportFormat.SVG,
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
        export_format: Output format (SVG, PNG, PDF).
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
        output_path = output_path.with_suffix(f".{export_format.value}")

    if method == ExportMethod.AUTO:
        # Try local first, fall back to online
        if _mmdc_available():
            try:
                return _export_local(
                    mermaid_code, output_path, export_format, background, theme, scale
                )
            except ExportError:
                # Local failed (e.g., missing Chrome for Puppeteer), try online
                pass
        return _export_online(mermaid_code, output_path, export_format, timeout, background)
    elif method == ExportMethod.LOCAL:
        if not _mmdc_available():
            raise ExportError(
                "mermaid-cli (mmdc) not found. Install with: npm install -g @mermaid-js/mermaid-cli"
            )
        return _export_local(
            mermaid_code, output_path, export_format, background, theme, scale
        )
    else:  # ONLINE
        return _export_online(mermaid_code, output_path, export_format, timeout, background)


def _mmdc_available() -> bool:
    """Check if mermaid-cli is installed."""
    return shutil.which("mmdc") is not None


def _export_local(
    mermaid_code: str,
    output_path: Path,
    export_format: ExportFormat,
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

        if export_format == ExportFormat.PNG:
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


def _get_imagemagick_command() -> str | None:
    """Get the ImageMagick command (magick for v7, convert for v6)."""
    if shutil.which("magick"):
        return "magick"
    if shutil.which("convert"):
        return "convert"
    return None


def _add_background_to_png(png_path: Path, background: str) -> None:
    """Add solid background to PNG using ImageMagick."""
    cmd = _get_imagemagick_command()
    if not cmd:
        return  # Silently skip if not available

    try:
        # Use ImageMagick to flatten with background color
        args = [cmd]
        if cmd == "magick":
            args.append("convert")  # magick convert for IMv7
        args.extend([
            str(png_path),
            "-background", background,
            "-flatten",
            str(png_path),
        ])
        subprocess.run(args, capture_output=True, timeout=30)
        # Ignore errors - just keep original if it fails
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def _export_online(
    mermaid_code: str,
    output_path: Path,
    export_format: ExportFormat,
    timeout: int,
    background: str = "white",
) -> Path:
    """Export using kroki.io API."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        pkg_version = version("pg2mermaid")
    except PackageNotFoundError:
        pkg_version = "0.1.0"

    url = f"https://kroki.io/mermaid/{export_format.value}"

    try:
        # Use POST with plain text body
        data = mermaid_code.encode("utf-8")
        request = Request(url, data=data, method="POST")
        request.add_header("Content-Type", "text/plain")
        request.add_header("Accept", f"image/{export_format.value}")
        request.add_header("User-Agent", f"pg2mermaid/{pkg_version}")

        with urlopen(request, timeout=timeout) as response:
            content = response.read()

        # For SVG, add background rectangle
        if export_format == ExportFormat.SVG:
            content = _add_background_to_svg(content, background)

        output_path.write_bytes(content)

        # For PNG, add background using ImageMagick (if available)
        if export_format == ExportFormat.PNG:
            _add_background_to_png(output_path, background)

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


def _add_background_to_svg(svg_content: bytes, background: str) -> bytes:
    """Add a background rectangle to an SVG."""
    svg_str = svg_content.decode("utf-8")

    # Determine dimensions from viewBox or width/height attributes
    viewbox_match: re.Match[str] | None = re.search(r'viewBox="([^"]+)"', svg_str)
    width_match: re.Match[str] | None = re.search(r'width="([^"]+)"', svg_str)
    height_match: re.Match[str] | None = re.search(r'height="([^"]+)"', svg_str)

    if viewbox_match:
        parts = viewbox_match.group(1).split()
        if len(parts) == 4:
            x, y, w, h = parts
            bg_rect = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{background}"/>'
        else:
            bg_rect = f'<rect x="0" y="0" width="100%" height="100%" fill="{background}"/>'
    elif width_match and height_match:
        w = width_match.group(1)
        h = height_match.group(1)
        bg_rect = f'<rect x="0" y="0" width="{w}" height="{h}" fill="{background}"/>'
    else:
        bg_rect = f'<rect x="0" y="0" width="100%" height="100%" fill="{background}"/>'

    # Insert background rect right after the opening <svg ...> tag.
    # This is more robust than searching for <g> tags, which may vary by generator.
    svg_open: re.Match[str] | None = re.search(r"<svg[^>]*>", svg_str)
    if svg_open:
        insert_pos = svg_open.end()
        svg_str = svg_str[:insert_pos] + bg_rect + svg_str[insert_pos:]
    else:
        # Should not happen with valid SVG, but handle gracefully
        svg_str = bg_rect + svg_str

    return svg_str.encode("utf-8")
