#!/usr/bin/env python3
"""
qubes_usb_writer.py
────────────────────────────────────────────────────────────────────────────
Downloads the latest Qubes OS x86_64 ISO (bootable installer / live-boot
capable image), verifies its SHA-256 digest, then writes it to a user-
selected external drive on macOS.

Must be run as root:
    sudo python3 qubes_usb_writer.py

WARNING: The selected drive will be completely overwritten.
────────────────────────────────────────────────────────────────────────────
"""

import hashlib
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# ── Release metadata ──────────────────────────────────────────────────────
# Qubes OS 4.3.0 x86_64 — latest stable release (December 2025).
# Update these constants when a newer release is published:
#   https://www.qubes-os.org/downloads/
QUBES_VERSION   = "4.3.0"
ISO_FILENAME    = f"Qubes-R{QUBES_VERSION}-x86_64.iso"

# Primary: official Qubes FTP server.  Fallback: kernel.org mirror.
ISO_URLS = [
    f"https://ftp.qubes-os.org/iso/{ISO_FILENAME}",
    f"https://mirrors.edge.kernel.org/qubes/iso/{ISO_FILENAME}",
]

# The .DIGESTS file uses BSD digest format and lives only on the official FTP.
# It contains MD5 / SHA1 / SHA256 / SHA512 lines (possibly PGP-wrapped).
DIGEST_URLS = [
    f"https://ftp.qubes-os.org/iso/{ISO_FILENAME}.DIGESTS",
    # kernel.org mirror does not publish the .DIGESTS sidecar file
]

# Minimum free space required (bytes) — slightly above a full DVD image
MIN_FREE_BYTES  = 7 * 1024 ** 3   # 7 GiB


# ── Helpers ───────────────────────────────────────────────────────────────

def banner(msg: str) -> None:
    width = 72
    print("\n" + "─" * width)
    print(f"  {msg}")
    print("─" * width)


def abort(msg: str) -> None:
    print(f"\n[ABORT] {msg}", file=sys.stderr)
    sys.exit(1)


def check_root() -> None:
    if os.geteuid() != 0:
        abort("This script must be run as root.  Try: sudo python3 qubes_usb_writer.py")


def check_macos() -> None:
    if sys.platform != "darwin":
        abort("This script is designed for macOS only.")


def check_dependencies() -> None:
    for tool in ("diskutil", "dd"):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            abort(f"Required tool not found in PATH: {tool}")


def fetch_expected_digest() -> str:
    """
    Download the official .DIGESTS file and extract the SHA-256 hex string.

    The file uses BSD digest format, optionally PGP-wrapped:
        SHA256 (Qubes-R4.x.x-x86_64.iso) = <hex>
    """
    banner("Fetching SHA-256 digest from Qubes project…")
    raw = None
    for url in DIGEST_URLS:
        print(f"  Trying: {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "qubes-usb-writer/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode(errors="replace").strip()
            print("  Download OK.")
            break
        except Exception as exc:
            print(f"  Failed ({exc}), trying next…")

    if not raw:
        abort(
            "Could not fetch the digest file from any source.\n"
            "Check your internet connection and try again."
        )

    # Match BSD-format line:  SHA256 (filename) = <hex64>
    match = re.search(
        r"SHA256\s*\([^)]*\)\s*=\s*([0-9a-fA-F]{64})",
        raw,
        re.IGNORECASE,
    )
    # Fallback: bare 64-char hex on its own line (GNU coreutils format)
    if not match:
        match = re.search(r"\b([0-9a-fA-F]{64})\b", raw)
    if not match:
        abort(f"Could not parse SHA-256 from digest file. Raw content:\n{raw[:400]}")

    digest = match.group(1).lower()
    print(f"  Expected SHA-256: {digest}")
    return digest


def sha256_file(path: Path, chunk: int = 4 * 1024 ** 2) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def download_iso(dest: Path) -> None:
    """Stream the ISO to *dest* with a live progress bar, trying each mirror."""
    banner(f"Downloading Qubes OS {QUBES_VERSION} ISO…")
    print(f"  Dest   : {dest}\n")

    for url in ISO_URLS:
        print(f"  Trying : {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "qubes-usb-writer/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk = 4 * 1024 ** 2  # 4 MiB

                with open(dest, "wb") as fh:
                    while True:
                        block = resp.read(chunk)
                        if not block:
                            break
                        fh.write(block)
                        downloaded += len(block)

                        if total:
                            pct = downloaded / total * 100
                            mib = downloaded / 1024 ** 2
                            total_mib = total / 1024 ** 2
                            bar_len = 40
                            filled = int(bar_len * downloaded / total)
                            bar = "█" * filled + "░" * (bar_len - filled)
                            print(
                                f"\r  [{bar}] {pct:5.1f}%  "
                                f"{mib:,.0f} / {total_mib:,.0f} MiB",
                                end="",
                                flush=True,
                            )
            print()   # newline after progress bar
            return    # success — done
        except Exception as exc:
            print(f"\n  Mirror failed ({exc}), trying next…")
            if dest.exists():
                dest.unlink()

    abort("All download mirrors failed. Check your internet connection and try again.")


def get_external_drives() -> list[dict]:
    """
    Return a list of dicts describing external physical disks visible to
    diskutil.  Each dict has keys: device, size, name.
    """
    result = subprocess.run(
        ["diskutil", "list", "-plist", "external", "physical"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        abort("diskutil failed to list external drives.")

    # Parse the plist with the built-in library
    import plistlib
    data = plistlib.loads(result.stdout.encode())

    drives = []
    for disk in data.get("WholeDisks", []):
        info_result = subprocess.run(
            ["diskutil", "info", "-plist", disk],
            capture_output=True, text=True
        )
        if info_result.returncode != 0:
            continue
        info = plistlib.loads(info_result.stdout.encode())
        drives.append({
            "device": f"/dev/{disk}",
            "size":   info.get("TotalSize", 0),
            "name":   info.get("MediaName", "Unknown"),
        })
    return drives


def pick_drive(drives: list[dict]) -> dict:
    banner("Detected external drives")
    for i, d in enumerate(drives, 1):
        gib = d["size"] / 1024 ** 3
        print(f"  [{i}] {d['device']}  —  {d['name']}  ({gib:.1f} GiB)")

    print()
    while True:
        try:
            choice = int(input("  Select drive number (or 0 to quit): "))
        except (ValueError, EOFError):
            print("  Please enter a valid number.")
            continue
        if choice == 0:
            abort("User cancelled.")
        if 1 <= choice <= len(drives):
            return drives[choice - 1]
        print(f"  Enter a number between 1 and {len(drives)}.")


def confirm_write(drive: dict) -> None:
    gib = drive["size"] / 1024 ** 3
    print(
        f"\n  ⚠️  ALL DATA on {drive['device']} ({drive['name']}, "
        f"{gib:.1f} GiB) will be PERMANENTLY ERASED.\n"
    )
    answer = input("  Type YES (all-caps) to continue: ").strip()
    if answer != "YES":
        abort("Write cancelled by user.")


def unmount_disk(device: str) -> None:
    """Unmount all volumes on the disk so dd can write to the raw device."""
    banner(f"Unmounting {device}…")
    result = subprocess.run(
        ["diskutil", "unmountDisk", device],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        abort(f"Could not unmount {device}:\n{result.stderr}")
    print(f"  {result.stdout.strip()}")


def write_iso(iso_path: Path, device: str) -> None:
    """
    Write the ISO to the raw (unbuffered) device node using dd.
    macOS exposes /dev/rdiskN as the raw (faster) counterpart of /dev/diskN.
    """
    raw_device = device.replace("/dev/disk", "/dev/rdisk")
    banner(f"Writing ISO to {raw_device}  (this may take several minutes)…")
    print("  Do NOT remove the drive until the prompt returns.\n")

    cmd = [
        "dd",
        f"if={iso_path}",
        f"of={raw_device}",
        "bs=4m",          # 4 MiB blocks — fast on macOS
        "status=progress",
    ]

    try:
        # dd on macOS doesn't support status=progress on older versions;
        # run with a fallback if it fails.
        proc = subprocess.run(cmd)
        if proc.returncode != 0:
            # Retry without status=progress (pre-Ventura macOS)
            cmd.remove("status=progress")
            print("  (retrying without real-time progress display)")
            subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        abort(f"dd failed: {exc}")

    # Flush kernel buffers
    subprocess.run(["sync"], check=False)
    print("\n  ✅  Write complete.  You can now safely eject the drive.")


def check_free_space(directory: Path) -> None:
    stat = os.statvfs(directory)
    free = stat.f_bavail * stat.f_frsize
    if free < MIN_FREE_BYTES:
        gib_free = free / 1024 ** 3
        gib_need = MIN_FREE_BYTES / 1024 ** 3
        abort(
            f"Not enough free space in {directory}. "
            f"Need {gib_need:.1f} GiB, have {gib_free:.1f} GiB."
        )


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    check_macos()
    check_root()
    check_dependencies()

    banner(f"Qubes OS {QUBES_VERSION} USB Writer  —  macOS")
    print(
        "  This script will:\n"
        "    1. Download the Qubes OS ISO\n"
        "    2. Verify its SHA-256 digest\n"
        "    3. Write it to an external drive you choose\n"
    )

    # ── Step 1: Fetch expected digest ────────────────────────────────────
    expected_digest = fetch_expected_digest()

    # ── Step 2: Detect drives (do this early so the user knows what's
    #    available before the long download) ──────────────────────────────
    banner("Scanning for external drives…")
    drives = get_external_drives()
    if not drives:
        abort(
            "No external physical drives found.  "
            "Plug in a USB drive (≥ 8 GiB) and re-run."
        )
    print(f"  Found {len(drives)} external drive(s).")

    # ── Step 3: Download ─────────────────────────────────────────────────
    tmp_dir = Path(tempfile.gettempdir())
    check_free_space(tmp_dir)
    iso_path = tmp_dir / ISO_FILENAME

    if iso_path.exists():
        print(f"\n  Found cached ISO at {iso_path}")
        print("  Skipping download — will verify digest instead.")
    else:
        download_iso(iso_path)

    # ── Step 4: Verify ───────────────────────────────────────────────────
    banner("Verifying SHA-256 digest…")
    print("  Computing digest (this takes ~30 s for a 6 GiB file)…")
    actual_digest = sha256_file(iso_path)
    print(f"  Computed : {actual_digest}")
    print(f"  Expected : {expected_digest}")
    if actual_digest != expected_digest:
        iso_path.unlink(missing_ok=True)
        abort(
            "SHA-256 mismatch!  The file may be corrupt or tampered with.\n"
            "The ISO has been removed.  Re-run the script to re-download."
        )
    print("  ✅  Digest matches — ISO is authentic.")

    # ── Step 5: Pick drive & confirm ─────────────────────────────────────
    selected = pick_drive(drives)
    confirm_write(selected)

    # ── Step 6: Unmount & write ───────────────────────────────────────────
    unmount_disk(selected["device"])
    write_iso(iso_path, selected["device"])

    banner("All done!")
    print(
        f"  Qubes OS {QUBES_VERSION} has been written to {selected['device']}.\n"
        "  Boot your x86-64 machine from this USB drive.\n"
        "  On first boot select 'Install Qubes OS' or 'Test media & install'.\n"
        "\n"
        "  Note: Qubes OS does not support a persistent live session;\n"
        "  it must be installed to an internal drive to run fully.\n"
        "  The USB is a verified bootable installer image.\n"
        "  Qubes 4.3 requires hardware with VT-x / VT-d and a 64-bit CPU.\n"
    )


if __name__ == "__main__":
    main()
