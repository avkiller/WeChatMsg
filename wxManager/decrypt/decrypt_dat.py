#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/9 23:44
@Author      : SiYuan
@Email       : 863909694@qq.com
@File        : wxManager-decrypt_dat.py
@Description : 微信4.0图片加密原理解析：https://blog.lc044.love/post/16
"""
import os
import struct
from typing import List, Tuple
from concurrent.futures import ProcessPoolExecutor
from aiofiles import open as aio_open
from aiofiles.os import makedirs

from Crypto.Cipher import AES

# 图片字节头信息，
# [0][1]为jpg头信息，
# [2][3]为png头信息，
# [4][5]为gif头信息
pic_head = (0xff, 0xd8, 0x89, 0x50, 0x47, 0x49)
# 解密码
decode_code = 0
decode_code_v4 = -1

AES_KEY_MAP = {
    b'\x07\x08V1\x08\x07': b'cfcd208495d565ef',  # 4.0第一代图片密钥
    b'\x07\x08V2\x08\x07': b'43e7d25eb1b9bb64',  # 4.0第二代图片密钥，微信4.0.3正式版使用
}


def get_aes_key(header):
    return AES_KEY_MAP.get(header[:6], b'')


def is_v4_image(header):
    return header[:6] in AES_KEY_MAP


def get_code(dat_read):
    """
    自动判断文件类型，并获取dat文件解密码
    :param file_path: dat文件路径
    :return: 如果文件为jpg/png/gif格式，则返回解密码，否则返回-1
    """
    try:
        if not dat_read:
            return -1, -1
        head_index = 0
        while head_index < len(pic_head):
            # 使用第一个头信息字节来计算加密码
            # 第二个字节来验证解密码是否正确
            code = dat_read[0] ^ pic_head[head_index]
            idf_code = dat_read[1] ^ code
            head_index = head_index + 1
            if idf_code == pic_head[head_index]:
                return head_index, code
            head_index = head_index + 1
        print("not jpg, png, gif")
        return -1, -1
    except:
        return -1, -1


def decode_dat(xor_key: int, file_path, out_path, dst_name='') -> str | bytes:
    """
    解密文件，并生成图片
    @param file_path: 输入文件路径
    @param out_path: 输出文件文件夹
    @param dst_name: 输出文件名
    :param xor_key: 异或加密密钥
    """
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        return ''
    if not os.path.exists(out_path):
        os.makedirs(out_path, exist_ok=True)
    if not os.path.isdir(out_path):
        return ''
    # print(file_path,out_path,dst_name)
    with open(file_path, 'rb') as file_in:
        header = file_in.read(0xf)
    if is_v4_image(header):
        # 微信4.0
        return decode_dat_v4(xor_key, file_path, out_path, dst_name)

    with open(file_path, 'rb') as file_in:
        header = file_in.read(2)
        file_type, decode_code = get_code(header)
        if decode_code == -1:
            return ''

        filename = os.path.basename(file_path)[:-4] if not dst_name else dst_name
        if file_type == 1:
            pic_name = filename + ".jpg"
        elif file_type == 3:
            pic_name = filename + ".png"
        elif file_type == 5:
            pic_name = filename + ".gif"
        else:
            pic_name = filename + ".jpg"

        file_outpath = os.path.join(out_path, pic_name)
        if os.path.exists(file_outpath):
            return file_outpath

        # 分块读取和写入
        buffer_size = 1024  # 定义缓冲区大小
        with open(file_outpath, 'wb') as file_out:
            file_out.write(bytes([byte ^ decode_code for byte in header]))
            while True:
                header = file_in.read(buffer_size)
                if not header:
                    break
                file_out.write(bytes([byte ^ decode_code for byte in header]))

    # print(os.path.basename(file_outpath))
    return file_outpath


def get_decode_code_v4(wx_dir):
    """
    从微信文件夹里找到异或密钥，原理详见：https://blog.lc044.love/post/16
    :param wx_dir:
    :return:
    """
    cache_dir = os.path.join(wx_dir, 'cache')
    if not os.path.isdir(wx_dir) or not os.path.exists(cache_dir):
        raise ValueError(f'微信路径输入错误，请检查：{wx_dir}')

    def find_xor_key(dir0):
        ok_flag = False
        for root, dirs, files in os.walk(dir0):
            if ok_flag:
                break
            for file in files:
                if file.endswith("_t.dat"):
                    # 构造源文件和目标文件的完整路径
                    src_file_path = os.path.join(root, file)
                    with open(src_file_path, 'rb') as f:
                        data = f.read()
                        if not is_v4_image(data):
                            continue
                        file_tail = data[-2:]

                        jpg_known_tail = b'\xff\xd9'
                        # 推导出密钥
                        xor_key = [c ^ p for c, p in zip(file_tail, jpg_known_tail)]
                        if len(set(xor_key)) == 1:
                            print(f'[*] 找到异或密钥: 0x{xor_key[0]:x}')
                            return xor_key[0]
        return -1

    xor_key_ = find_xor_key(cache_dir)
    if xor_key_ != -1:
        return xor_key_
    else:
        dirs = ['temp', 'msg']
        for dir_name in dirs:
            cache_dir = os.path.join(wx_dir, dir_name)
            xor_key_ = find_xor_key(cache_dir)
            if xor_key_ != -1:
                return xor_key_
    return 0


def get_image_type(data: bytes) -> str:
    """
    根据文件头字节判断图片类型
    :param data: 文件头数据（通常至少需要前 10 个字节）
    :return: 图片类型（扩展名），默认为 'bin'
    """
    if data.startswith(b'\xff\xd8\xff'):
        return 'jpg'  # JPEG 文件
    elif data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'  # PNG 文件
    elif data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return 'gif'  # GIF 文件
    elif data.startswith(b'BM'):
        return 'bmp'  # BMP 文件
    elif data.startswith(b'II*\x00') or data.startswith(b'MM\x00*'):
        return 'tiff'  # TIFF 文件
    elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return 'webp'  # WEBP 文件
    elif data.startswith(b'\x00\x00\x01\x00'):
        return 'ico'  # ICO 文件
    else:
        return 'bin'  # 未知类型，返回二进制


def decode_dat_v4(xor_key: int, file_path, out_path, dst_name='') -> str | bytes:
    """
    适用于微信4.0图片.dat，解密文件，并生成图片
    :param xor_key: int 异或密钥
    :param file_path: dat文件路径
    :param out_path: 输出文件夹
    :param dst_name: 输出文件名，默认为输入文件名
    :return:
    """

    if not os.path.exists(file_path) or os.path.isdir(file_path):
        return ''

    # 读取加密文件的内容
    with open(file_path, 'rb') as f:
        header = f.read(0xf)
        encrypt_length = struct.unpack_from('<H', header, 6)[0]
        encrypt_length0 = encrypt_length // 16 * 16 + 16
        encrypted_data = f.read(encrypt_length0)
        res_data = f.read()

    # 如果数据不是16的倍数，填充0
    if len(encrypted_data) % 16 != 0:
        padding_length = 16 - (len(encrypted_data) % 16)
        encrypted_data += b'\x00' * padding_length

    aes_key = get_aes_key(header)

    # 初始化AES解密器（ECB模式）
    cipher = AES.new(aes_key, AES.MODE_ECB)

    # 解密数据
    decrypted_data = cipher.decrypt(encrypted_data)

    # 获取图片后缀名
    image_type = get_image_type(decrypted_data[:10])
    output_file_name = os.path.basename(file_path)[:-4] if not dst_name else dst_name
    output_file = os.path.join(out_path, output_file_name + '.' + image_type)
    if os.path.exists(output_file):
        return output_file

    # 移除填充（假设使用的是PKCS7或PKCS5填充）
    pad_length = decrypted_data[-1]  # 获取填充长度
    decrypted_data = decrypted_data[:-pad_length]

    # 将解密后的数据写入输出文件
    with open(output_file, 'wb') as f:
        f.write(decrypted_data)
        f.write(res_data[0:-0x100000])
        f.write(bytes([byte ^ xor_key for byte in res_data[-0x100000:]]))

    # print(f"解密完成，已保存到: {output_file}")
    return output_file


async def decode_dat_v4_async(xor_key: int, file_path, out_path, dst_name='') -> str:
    """
    异步版本的微信4.0图片 .dat 文件解密器
    :param xor_key: int 异或密钥
    :param file_path: .dat 文件路径
    :param out_path: 输出文件夹
    :param dst_name: 输出文件名，默认为输入文件名
    :return: 解密后的文件路径
    """
    if not os.path.exists(file_path):
        return ''

    # 确保输出目录存在
    await makedirs(out_path, exist_ok=True)

    # 读取加密文件的内容
    async with aio_open(file_path, 'rb') as f:
        header = await f.read(0xf)
        encrypt_length = struct.unpack_from('<H', header, 6)[0]
        encrypt_length0 = encrypt_length // 16 * 16 + 16
        encrypted_data = await f.read(encrypt_length0)
        res_data = await f.read()

    aes_key = get_aes_key(header)

    # 初始化AES解密器（ECB模式）
    cipher = AES.new(aes_key, AES.MODE_ECB)

    # 解密数据
    decrypted_data = cipher.decrypt(encrypted_data)

    # 获取图片后缀名
    image_type = get_image_type(decrypted_data[:10])
    output_file_name = os.path.basename(file_path)[:-4] if not dst_name else dst_name
    output_file = os.path.join(out_path, output_file_name + '.' + image_type)

    if os.path.exists(output_file):
        return output_file

    # 移除填充（假设使用的是PKCS7或PKCS5填充）
    pad_length = decrypted_data[-1]  # 获取填充长度
    decrypted_data = decrypted_data[:-pad_length]

    # 将解密后的数据写入输出文件
    async with aio_open(output_file, 'wb') as f:
        await f.write(decrypted_data)
        await f.write(res_data[:-0x100000])
        await f.write(bytes([byte ^ xor_key for byte in res_data[-0x100000:]]))

    print(f"解密完成，已保存到: {output_file}")
    return output_file


def decode_wrapper(tasks):
    """用于包装解码函数的顶层定义"""
    # results = []
    # for args in tasks:
    #     results.append(decode_dat(*args))
    # return results

    return decode_dat(*tasks)


def batch_decode_image_multiprocessing(xor_key, file_infos: List[Tuple[str, str, str]]):
    """

    :param xor_key: 异或加密密钥
    :param file_infos: 文件信息列表
    item: [input_path: 输入图片路径
            output_dir: 输出图片文件夹
            dst_name: 输出文件名]
    :return:
    """
    if len(file_infos) < 1:
        return

    def split_list(lst, n):
        k, m = divmod(len(lst), n)
        return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

    with ProcessPoolExecutor(max_workers=10) as executor:
        tasks = [(xor_key, file_path, out_path, file_name) for file_path, out_path, file_name in file_infos]
        # print(len(split_list(tasks, 10)), '总任务数', len(file_infos))
        results = list(executor.map(decode_wrapper, tasks, chunksize=200))  # 使用顶层定义的函数
    return results


if __name__ == '__main__':
    wx_dir = ''
    xor_key = get_decode_code_v4(wx_dir)
    dat_file = "1c5d8c0cf05d97869b0bc9fe16a8e3c2.dat"
    decode_dat_v4(xor_key, dat_file, '.', dst_name='解密后的图片')
