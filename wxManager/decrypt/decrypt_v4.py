import hmac
import os
import struct
from concurrent.futures import ProcessPoolExecutor

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA512

# Constants
IV_SIZE = 16
HMAC_SHA256_SIZE = 64
KEY_SIZE = 32
AES_BLOCK_SIZE = 16
ROUND_COUNT = 256000
PAGE_SIZE = 4096
SALT_SIZE = 16
SQLITE_HEADER = b"SQLite format 3"


def decrypt_db_file_v4(pkey, in_db_path, out_db_path):
    if not os.path.exists(in_db_path):
        print(f"【!!!】{in_db_path} does not exist.")
        return False

    with open(in_db_path, 'rb') as f_in, open(out_db_path, 'wb') as f_out:
        # Read salt from the first SALT_SIZE bytes
        salt = f_in.read(SALT_SIZE)
        if not salt:
            print("File is empty or corrupted.")
            return False

        mac_salt = bytes(x ^ 0x3a for x in salt)

        # Convert pkey from hex to bytes
        passphrase = bytes.fromhex(pkey)

        # Use PBKDF2 to derive key and mac_key
        key = PBKDF2(passphrase, salt, dkLen=KEY_SIZE, count=ROUND_COUNT, hmac_hash_module=SHA512)
        mac_key = PBKDF2(key, mac_salt, dkLen=KEY_SIZE, count=2, hmac_hash_module=SHA512)

        # Write SQLITE_HEADER to the output file
        f_out.write(SQLITE_HEADER)
        f_out.write(b'\x00')

        # Reserve space for IV_SIZE + HMAC_SHA256_SIZE, rounded to a multiple of AES_BLOCK_SIZE
        reserve = IV_SIZE + HMAC_SHA256_SIZE
        reserve = ((reserve + AES_BLOCK_SIZE - 1) // AES_BLOCK_SIZE) * AES_BLOCK_SIZE

        # Process each page
        cur_page = 0
        while True:

            # For the first page, include SALT_SIZE adjustment
            if cur_page == 0:
                # Read one full PAGE_SIZE starting from after the salt
                page = f_in.read(PAGE_SIZE - SALT_SIZE)
                if not page:
                    break  # No more data
                page = salt + page  # Include the salt in the first page data
            else:
                page = f_in.read(PAGE_SIZE)
            if not page:
                break  # End of file
            # print(f'第{cur_page + 1}页')
            offset = SALT_SIZE if cur_page == 0 else 0
            end = len(page)

            # If the page is all zero bytes, append it directly and exit
            if all(x == 0 for x in page):
                f_out.write(page)
                print("Exiting early due to zeroed page.")
                break

            # Perform HMAC check
            mac = hmac.new(mac_key, page[offset:end - reserve + IV_SIZE], SHA512)
            mac.update(struct.pack('<I', cur_page + 1))  # Add page number
            hash_mac = mac.digest()

            # Check if HMAC matches
            hash_mac_start_offset = end - reserve + IV_SIZE
            if hash_mac != page[hash_mac_start_offset:hash_mac_start_offset + len(hash_mac)]:
                print(f'Key error: {key}')
                return None
                raise ValueError("Hash verification failed")

            # AES-256-CBC decryption
            iv = page[end - reserve:end - reserve + IV_SIZE]
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted_data = cipher.decrypt(page[offset:end - reserve])

            # Remove padding
            pad_len = decrypted_data[-1]
            # decrypted_data = decrypted_data[:-pad_len]

            # Write decrypted data and HMAC/IV to output
            f_out.write(decrypted_data)
            f_out.write(page[end - reserve:end])

            cur_page += 1

    print("Decryption completed.")
    return True


def decode_wrapper(tasks):
    """用于包装解码函数的顶层定义"""
    return decrypt_db_file_v4(*tasks)


def decrypt_db_files(key, src_dir: str, dest_dir: str):
    if not os.path.exists(src_dir):
        print(f"源文件夹 {src_dir} 不存在")
        return

    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)  # 如果目标文件夹不存在，创建它
    decrypt_tasks = []
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".db"):
                # 构造源文件和目标文件的完整路径
                src_file_path = os.path.join(root, file)

                # 计算目标路径，保持子文件夹结构
                relative_path = os.path.relpath(root, src_dir)
                dest_sub_dir = os.path.join(dest_dir, relative_path)
                dest_file_path = os.path.join(dest_sub_dir, file)

                # 确保目标子文件夹存在
                if not os.path.exists(dest_sub_dir):
                    os.makedirs(dest_sub_dir)
                print(dest_file_path)
                decrypt_tasks.append((key, src_file_path, dest_file_path))
                # decrypt_db_file_v4(key, src_file_path, dest_file_path)
    with ProcessPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(decode_wrapper, decrypt_tasks))  # 使用顶层定义的函数
