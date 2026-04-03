# qubes_usb_writer

A single-file Python script for macOS that downloads the latest **Qubes OS** x86-64 ISO, verifies its SHA-256 digest against the official Qubes checksum, and writes it to a USB drive — all in one command.

---

## Requirements

| Requirement | Notes |
|---|---|
| macOS | Tested on Ventura and later. Should work back to Catalina. |
| Python 3.9+ | Ships with macOS. No third-party packages required. |
| Root privileges | Needed to write to raw block devices via `dd`. |
| External USB drive | 8 GiB minimum recommended. **All data will be erased.** |
| ~7 GiB free in `/tmp` | The ISO is staged here before writing. |
| Internet connection | Required to fetch the ISO (~7 GiB) and checksum file. |

No `brew`, `pip install`, or extra dependencies needed — the script uses only Python's standard library.

---

## Usage

```bash
sudo python3 qubes_usb_writer.py
```

The script is fully interactive. It will:

1. Fetch the official SHA-256 digest from `ftp.qubes-os.org`
2. Scan for attached external drives and display a numbered list
3. Download the ISO with a live progress bar (skipped if already cached in `/tmp`)
4. Verify the ISO's SHA-256 digest — aborts and deletes the file on mismatch
5. Ask you to select the target drive and confirm with `YES`
6. Unmount the drive and write the ISO using `dd` at 4 MiB/block

---

## What gets written

The script writes **Qubes OS 4.3.0** (`Qubes-R4.3.0-x86_64.iso`), the current stable release as of December 2025. The resulting USB drive is a bootable installer image.

> **Note on "live" mode:** Qubes OS does not support a persistent live session. Its architecture — Xen hypervisor + multiple isolated VMs — requires installation to an internal drive. The USB lets you boot any x86-64 machine, run the installer, and optionally test media first. A full installation to internal storage is required to use Qubes normally.

---

## Safety features

**Digest verification** — The script downloads the `.DIGESTS` file directly from the Qubes project FTP server and extracts the SHA-256 hash. It computes the hash of the downloaded ISO locally and aborts with a hard error if they don't match. The ISO is deleted in that case so a corrupted file is never silently written to disk.

**Internal drives are never shown** — Drive discovery uses `diskutil list external physical`, which only surfaces drives the OS has classified as external. Your Mac's internal SSD will never appear in the selection list.

**Explicit confirmation** — Before any data is written you must select a numbered drive from the list and then type `YES` in all-caps. Any other input cancels.

**Mirror fallback** — Both the ISO download and the digest fetch loop through a list of mirrors. If the primary source (`ftp.qubes-os.org`) is unavailable, the script automatically retries on `mirrors.edge.kernel.org`.

**Download caching** — If the ISO already exists in `/tmp` from a previous run, the download step is skipped and only the digest re-verification is performed.

---

## Example session

```
────────────────────────────────────────────────────────────────────────
  Qubes OS 4.3.0 USB Writer  —  macOS
────────────────────────────────────────────────────────────────────────
  This script will:
    1. Download the Qubes OS ISO
    2. Verify its SHA-256 digest
    3. Write it to an external drive you choose

────────────────────────────────────────────────────────────────────────
  Fetching SHA-256 digest from Qubes project…
────────────────────────────────────────────────────────────────────────
  Trying: https://ftp.qubes-os.org/iso/Qubes-R4.3.0-x86_64.iso.DIGESTS
  Download OK.
  Expected SHA-256: a3f0...e91c

────────────────────────────────────────────────────────────────────────
  Scanning for external drives…
────────────────────────────────────────────────────────────────────────
  Found 1 external drive(s).

────────────────────────────────────────────────────────────────────────
  Downloading Qubes OS 4.3.0 ISO…
────────────────────────────────────────────────────────────────────────
  Trying : https://ftp.qubes-os.org/iso/Qubes-R4.3.0-x86_64.iso
  [████████████████████░░░░░░░░░░░░░░░░░░░░]  51.3%  3,412 / 6,650 MiB

────────────────────────────────────────────────────────────────────────
  Verifying SHA-256 digest…
────────────────────────────────────────────────────────────────────────
  Computing digest (this takes ~30 s for a 6 GiB file)…
  Computed : a3f0...e91c
  Expected : a3f0...e91c
  ✅  Digest matches — ISO is authentic.

────────────────────────────────────────────────────────────────────────
  Detected external drives
────────────────────────────────────────────────────────────────────────
  [1] /dev/disk4  —  SanDisk Ultra USB 3.0 Media  (28.7 GiB)

  Select drive number (or 0 to quit): 1

  ⚠️  ALL DATA on /dev/disk4 (SanDisk Ultra USB 3.0 Media, 28.7 GiB)
     will be PERMANENTLY ERASED.

  Type YES (all-caps) to continue: YES
```

---

## Updating to a newer Qubes release

Edit the `QUBES_VERSION` constant near the top of the script:

```python
QUBES_VERSION = "4.3.0"   # ← change this
```

The `ISO_FILENAME`, `ISO_URLS`, and `DIGEST_URLS` are all derived from this value automatically. Check the [Qubes OS downloads page](https://www.qubes-os.org/downloads/) for the latest release.

---

## Target hardware requirements (for the machine you'll install Qubes on)

| Component | Minimum |
|---|---|
| CPU | 64-bit Intel or AMD with **VT-x** (Intel) or **AMD-V** |
| IOMMU | **VT-d** (Intel) or **AMD-Vi** strongly recommended |
| RAM | 16 GiB recommended (8 GiB absolute minimum) |
| Storage | 64 GiB internal drive (SSD strongly recommended) |
| Boot mode | UEFI or legacy BIOS |

Qubes will boot from the USB on any x86-64 machine that meets these requirements, regardless of the OS currently installed on it.

---

## License

Public domain / unlicense. Use at your own risk.
