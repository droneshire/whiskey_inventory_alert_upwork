import argparse
import base64
import getpass
import os

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto import Random

ENCRYPT_PASSWORD_ENV_VAR = "ENCRYPT_PASSWORD"


def encrypt(key: bytes, source: bytes, encode: bool = True):
    key = SHA256.new(key).digest()
    IV = Random.new().read(AES.block_size)
    encryptor = AES.new(key, AES.MODE_CBC, IV)
    padding = AES.block_size - len(source) % AES.block_size
    source += bytes([padding]) * padding
    data = IV + encryptor.encrypt(source)
    return base64.b64encode(data).decode("latin-1") if encode else data


def decrypt(key: bytes, source: str, decode: bool = True):
    if decode:
        source = base64.b64decode(source.encode("latin-1"))
    key = SHA256.new(key).digest()
    IV = source[: AES.block_size]
    decryptor = AES.new(key, AES.MODE_CBC, IV)
    data = decryptor.decrypt(source[AES.block_size :])
    padding = data[-1]
    if data[-padding:] != bytes([padding]) * padding:
        raise ValueError("Invalid padding...")
    return data[:-padding]


def decrypt_secret(encrypt_password: str, encrypted_secret: str) -> str:
    if not encrypt_password:
        return ""
    return decrypt(str.encode(encrypt_password), encrypted_secret).decode()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--encrypt", action="store_true")
    group.add_argument("--decrypt", action="store_true")
    options = parser.parse_args()

    key_str = os.getenv(ENCRYPT_PASSWORD_ENV_VAR)
    if not key_str:
        key_str = getpass.getpass(prompt="Enter decryption password: ")
    byte_key = str.encode(key_str)
    data_str = input("Enter data to encrypt/decrypt: ")
    if options.encrypt:
        output = encrypt(byte_key, str.encode(data_str), encode=True)
    else:
        output = decrypt(byte_key, data_str, decode=True).decode()
    print(output)
