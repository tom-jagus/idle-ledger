#!/usr/bin/env sh
set -eu

REPO="tom-jagus/idle-ledger"
ASSET_TGZ="idle-ledger-linux-x86_64.tar.gz"
ASSET_SHA="idle-ledger-linux-x86_64.sha256"
BASE_URL="https://github.com/${REPO}/releases/latest/download"

# Basic platform check
OS="$(uname -s)"
ARCH="$(uname -m)"
if [ "$OS" != "Linux" ]; then
	echo "idle-ledger installer: Linux only (got $OS)" >&2
	exit 1
fi
if [ "$ARCH" != "x86_64" ]; then
	echo "idle-ledger installer: x86_64 only (got $ARCH)" >&2
	exit 1
fi

INSTALL_DIR="${HOME}/.local/bin"
INSTALL_PATH="${INSTALL_DIR}/idle-ledger"
TMP_DIR="$(mktemp -d)"

cleanup() {
	rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$INSTALL_DIR"

if command -v curl >/dev/null 2>&1; then
	FETCH="curl -fsSL"
elif command -v wget >/dev/null 2>&1; then
	FETCH="wget -qO-"
else
	echo "Need curl or wget" >&2
	exit 1
fi

TGZ_PATH="${TMP_DIR}/${ASSET_TGZ}"
SHA_PATH="${TMP_DIR}/${ASSET_SHA}"

echo "Downloading ${ASSET_TGZ} from ${BASE_URL}..."
$FETCH "${BASE_URL}/${ASSET_TGZ}" >"$TGZ_PATH"
$FETCH "${BASE_URL}/${ASSET_SHA}" >"$SHA_PATH"

if command -v sha256sum >/dev/null 2>&1; then
	(cd "$TMP_DIR" && sha256sum -c "$ASSET_SHA")
elif command -v shasum >/dev/null 2>&1; then
	EXPECTED="$(cut -d' ' -f1 <"$SHA_PATH")"
	ACTUAL="$(shasum -a 256 "$TGZ_PATH" | cut -d' ' -f1)"
	if [ "$EXPECTED" != "$ACTUAL" ]; then
		echo "SHA256 mismatch" >&2
		exit 1
	fi
else
	echo "Need sha256sum (or shasum) to verify download" >&2
	exit 1
fi

echo "Installing to ${INSTALL_PATH}..."
# tar should contain a single file: idle-ledger
TAR_DIR="${TMP_DIR}/tar"
mkdir -p "$TAR_DIR"
tar -xzf "$TGZ_PATH" -C "$TAR_DIR"

if [ ! -f "${TAR_DIR}/idle-ledger" ]; then
	echo "Archive did not contain expected 'idle-ledger' binary" >&2
	exit 1
fi

chmod +x "${TAR_DIR}/idle-ledger"
# Atomic-ish install
cp "${TAR_DIR}/idle-ledger" "${INSTALL_PATH}.tmp"
chmod +x "${INSTALL_PATH}.tmp"
mv "${INSTALL_PATH}.tmp" "$INSTALL_PATH"

echo "Installed: ${INSTALL_PATH}"

if ! command -v idle-ledger >/dev/null 2>&1; then
	echo "Note: ~/.local/bin may not be in your PATH." >&2
	echo "Add this to your shell config:" >&2
	echo "  export PATH=\"$HOME/.local/bin:$PATH\"" >&2
fi

echo "Next steps:"
echo "  idle-ledger --help"
echo "  idle-ledger init    # enable systemd user service"
