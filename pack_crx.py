"""
ShopSpy — Extension Packager

Builds the extension into dist/:
  dist/shopspy.zip  — for Chrome / Yandex Browser (unpack & load)
  dist/shopspy.crx  — for Yandex Browser (drag & drop), requires `cryptography`

Usage:
    python pack_crx.py
"""

import os
import struct
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

# ── Paths (all output goes to dist/) ──────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
EXTENSION_DIR = PROJECT_ROOT / "extension"
DIST_DIR = PROJECT_ROOT / "dist"
OUTPUT_ZIP = DIST_DIR / "shopspy.zip"
OUTPUT_CRX = DIST_DIR / "shopspy.crx"
KEY_FILE = PROJECT_ROOT / "shopspy.pem"

# ── Optional: cryptography for CRX signing ────────────────────

try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


# ── Helpers ────────────────────────────────────────────────────


def make_zip(ext_dir: Path, zip_path: Path) -> None:
    """Pack extension/ into a ZIP archive."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for file_path in sorted(ext_dir.rglob("*")):
            if file_path.is_file() and not file_path.name.startswith("."):
                zf.write(file_path, file_path.relative_to(ext_dir))
    size_kb = zip_path.stat().st_size / 1024
    print(f"  ✅ ZIP: {zip_path}  ({size_kb:.1f} KB)")


def make_crx(ext_dir: Path, crx_path: Path, key_path: Path) -> bool:
    """Pack extension/ into a signed CRX2 file (Yandex Browser compatible)."""
    if not HAS_CRYPTO:
        print("  ⚠️  cryptography не установлена — CRX не создан.")
        print("     pip install cryptography")
        return False

    # Load or generate RSA key
    if key_path.exists():
        private_key = serialization.load_pem_private_key(
            key_path.read_bytes(), password=None
        )
        print(f"  Ключ загружен: {key_path}")
    else:
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        key_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        print(f"  Ключ сгенерирован: {key_path}")

    # Build ZIP in memory
    tmp_zip = crx_path.with_suffix(".crx.zip")
    make_zip(ext_dir, tmp_zip)
    zip_data = tmp_zip.read_bytes()
    tmp_zip.unlink()

    # Public key (DER) + signature
    public_key_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = private_key.sign(zip_data, padding.PKCS1v15(), hashes.SHA256())

    # Write CRX2 binary
    crx_path.parent.mkdir(parents=True, exist_ok=True)
    with open(crx_path, "wb") as f:
        f.write(b"Cr24")
        f.write(struct.pack("<I", 2))  # CRX version 2
        f.write(struct.pack("<I", len(public_key_der)))
        f.write(struct.pack("<I", len(signature)))
        f.write(public_key_der)
        f.write(signature)
        f.write(zip_data)

    size_kb = crx_path.stat().st_size / 1024
    print(f"  ✅ CRX: {crx_path}  ({size_kb:.1f} KB)")
    return True


# ── Main ───────────────────────────────────────────────────────


def main():
    print()
    print("=" * 50)
    print("  ShopSpy — Extension Packager")
    print("=" * 50)
    print()

    if not EXTENSION_DIR.exists():
        print(f"  ❌ Папка {EXTENSION_DIR} не найдена!")
        return

    print("[1] ZIP-архив...")
    make_zip(EXTENSION_DIR, OUTPUT_ZIP)

    print()
    print("[2] CRX-файл...")
    crx_ok = make_crx(EXTENSION_DIR, OUTPUT_CRX, KEY_FILE)

    print()
    print("=" * 50)
    print("  Установка расширения")
    print("=" * 50)
    print()
    print("  Chrome / Edge:")
    print("    1. chrome://extensions/ → Режим разработчика")
    print("    2. «Загрузить распакованное» → папка extension/")
    print()
    print("  Яндекс.Браузер (ZIP):")
    print("    1. Распакуйте dist/shopspy.zip в папку")
    print("    2. browser://tune → перетащите ПАПКУ")
    print()
    if crx_ok:
        print("  Яндекс.Браузер (CRX):")
        print("    1. browser://tune → перетащите dist/shopspy.crx")
        print()


if __name__ == "__main__":
    main()
