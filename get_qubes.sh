#!/bin/bash

# Configuration
QUBES_REL="4.2.1" # Update this to the current version you want
ISO_NAME="Qubes-R$QUBES_REL-x86_64.iso"
SIG_NAME="$ISO_NAME.asc"
BASE_URL="https://mirrors.edge.kernel.org/qubes/iso" # High speed mirror

# 1. Check for GPG (Required for authenticity)
if ! command -v gpg &> /dev/null; then
    echo "[-] GPG is not installed. Run 'brew install gnupg' first."
    exit 1
fi

# 2. Download ISO and Signature
echo "[+] Downloading Qubes OS ISO and Signature..."
curl -L -O "$BASE_URL/$ISO_NAME"
curl -L -O "$BASE_URL/$SIG_NAME"

# 3. Import Qubes Master Signing Key
# Fingerprint: 427F 11FD 0FAA 4B08 0123 F01C DDFA 1A3E 3687 9494
echo "[+] Fetching Qubes Master Signing Key..."
gpg --fetch-keys https://keys.qubes-os.org/keys/qubes-master-signing-key.asc

# 4. Verify ISO Signature
echo "[+] Verifying Signature..."
# Note: This will likely give a 'Warning' that the key is not trusted.
# As a pro, you know this just means you haven't signed the master key yourself.
# We are looking for the 'Good signature' text.
gpg --verify "$SIG_NAME" "$ISO_NAME"

# 5. Verify Hash (Integrity Check)
echo "[+] Calculating SHA256 Hash..."
LOCAL_HASH=$(shasum -a 256 "$ISO_NAME" | awk '{print $1}')
echo "Local Hash:  $LOCAL_HASH"
echo "Check this against the website to be 100% sure of integrity."
