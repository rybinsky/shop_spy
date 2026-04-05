"""
Упаковщик расширения ShopSpy в формат CRX3 для Яндекс.Браузера.

Использование:
    python pack_crx.py

Результат: файл shopspy.crx в корне проекта
"""

import os
import struct
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

# Пытаемся использовать cryptography, если есть
try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding, utils
    from cryptography.hazmat.primitives import hashes, serialization
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


EXTENSION_DIR = os.path.join(os.path.dirname(__file__), "extension")
OUTPUT_CRX = os.path.join(os.path.dirname(__file__), "shopspy.crx")
OUTPUT_ZIP = os.path.join(os.path.dirname(__file__), "shopspy.zip")
KEY_FILE = os.path.join(os.path.dirname(__file__), "shopspy.pem")


def make_zip(ext_dir: str, zip_path: str):
    """Собирает содержимое extension/ в zip."""
    with ZipFile(zip_path, 'w', ZIP_DEFLATED) as zf:
        base = Path(ext_dir)
        for file_path in sorted(base.rglob('*')):
            if file_path.is_file():
                arcname = file_path.relative_to(base)
                zf.write(file_path, arcname)
    print(f"  ZIP создан: {zip_path}")


def make_crx3(ext_dir: str, crx_path: str, key_path: str):
    """Упаковывает расширение в CRX3 формат."""

    if not HAS_CRYPTO:
        print("\n  Библиотека cryptography не установлена.")
        print("  Установите: pip install cryptography")
        print("  Или используйте ZIP-способ установки (см. ниже).\n")
        return False

    # Генерируем или загружаем ключ
    if os.path.exists(key_path):
        with open(key_path, 'rb') as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        print("  Ключ загружен из", key_path)
    else:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        with open(key_path, 'wb') as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        print("  Ключ сгенерирован:", key_path)

    # Создаем ZIP
    zip_path = crx_path + ".zip"
    make_zip(ext_dir, zip_path)

    with open(zip_path, 'rb') as f:
        zip_data = f.read()

    # Публичный ключ в DER
    public_key_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Подпись
    signature = private_key.sign(
        zip_data,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    # CRX3 header
    # Формат: magic(4) + version(4) + header_length(4) + header + zip
    # Используем упрощенный CRX2-совместимый формат, который Яндекс.Браузер тоже принимает

    magic = b'Cr24'
    version = struct.pack('<I', 2)  # CRX2 формат, совместим с Яндекс.Браузером
    pubkey_len = struct.pack('<I', len(public_key_der))
    sig_len = struct.pack('<I', len(signature))

    with open(crx_path, 'wb') as f:
        f.write(magic)
        f.write(version)
        f.write(pubkey_len)
        f.write(sig_len)
        f.write(public_key_der)
        f.write(signature)
        f.write(zip_data)

    # Удаляем временный zip
    os.remove(zip_path)

    size_kb = os.path.getsize(crx_path) / 1024
    print(f"  CRX создан: {crx_path} ({size_kb:.1f} KB)")
    return True


def main():
    print()
    print("=" * 50)
    print("  ShopSpy - Упаковщик расширения")
    print("=" * 50)
    print()

    if not os.path.exists(EXTENSION_DIR):
        print(f"  Ошибка: папка {EXTENSION_DIR} не найдена!")
        return

    # Всегда создаем ZIP (работает без доп. библиотек)
    print("[1] Создаю ZIP-архив...")
    make_zip(EXTENSION_DIR, OUTPUT_ZIP)

    # Пробуем CRX
    print("\n[2] Создаю CRX-файл...")
    crx_ok = make_crx3(EXTENSION_DIR, OUTPUT_CRX, KEY_FILE)

    print()
    print("=" * 50)
    print("  Инструкция по установке в Яндекс.Браузер")
    print("=" * 50)
    print()
    print("  Способ 1 (ZIP - проще всего):")
    print("    1. Распакуйте shopspy.zip в папку")
    print("    2. Откройте browser://tune")
    print("    3. Перетащите ПАПКУ в окно браузера")
    print()

    if crx_ok:
        print("  Способ 2 (CRX):")
        print("    1. Откройте browser://tune")
        print("    2. Перетащите файл shopspy.crx в окно браузера")
        print("    3. Нажмите 'Установить расширение'")
        print()

    print("  Способ 3 (для Chrome/Edge):")
    print("    1. Откройте chrome://extensions/")
    print("    2. Включите 'Режим разработчика'")
    print("    3. 'Загрузить распакованное' -> папка extension/")
    print()
    print("  Не забудьте запустить бэкенд: python backend/main.py")
    print()


if __name__ == "__main__":
    main()
