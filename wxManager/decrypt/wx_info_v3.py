#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2025/3/7 16:30 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-wx_info_v3.py 
@Description : 
"""

# -*- coding: utf-8 -*-#
# -------------------------------------------------------------------------------
# Name:         getwxinfo.py
# Description:
# Author:       xaoyaoo
# Date:         2023/08/21
# -------------------------------------------------------------------------------

import os
import sys
import hmac
import hashlib
import ctypes
import winreg
import pymem
import pythoncom
import psutil
import pymem.process

from wxManager.decrypt.common import WeChatInfo
from wxManager.decrypt.common import get_version

ReadProcessMemory = ctypes.windll.kernel32.ReadProcessMemory
void_p = ctypes.c_void_p


def get_exe_bit(file_path):
    try:
        with open(file_path, 'rb') as f:
            dos_header = f.read(2)
            if dos_header != b'MZ':
                print('get exe bit error: Invalid PE file')
                return 64
            # Seek to the offset of the PE signature
            f.seek(60)
            pe_offset_bytes = f.read(4)
            pe_offset = int.from_bytes(pe_offset_bytes, byteorder='little')

            # Seek to the Machine field in the PE header
            f.seek(pe_offset + 4)
            machine_bytes = f.read(2)
            machine = int.from_bytes(machine_bytes, byteorder='little')

            if machine == 0x14c:
                return 32
            elif machine == 0x8664:
                return 64
            else:
                return 64
    except:
        return 64


def get_info_without_key(h_process, address, n_size=64):
    array = ctypes.create_string_buffer(n_size)
    if ReadProcessMemory(h_process, void_p(address), array, n_size, 0) == 0: return "None"
    array = bytes(array).split(b"\x00")[0] if b"\x00" in array else bytes(array)
    text = array.decode('utf-8', errors='ignore')
    return text.strip() if text.strip() != "" else "None"


def pattern_scan_all(handle, pattern, *, return_multiple=False, find_num=100):
    next_region = 0
    found = []
    user_space_limit = 0x7FFFFFFF0000 if sys.maxsize > 2 ** 32 else 0x7fff0000
    while next_region < user_space_limit:
        try:
            next_region, page_found = pymem.pattern.scan_pattern_page(
                handle,
                next_region,
                pattern,
                return_multiple=return_multiple
            )
        except Exception as e:
            print(e)
            break
        if not return_multiple and page_found:
            return page_found
        if page_found:
            found += page_found
        if len(found) > find_num:
            break
    return found


def get_info_wxid(h_process):
    find_num = 100
    addrs = pattern_scan_all(h_process, br'\\Msg\\FTSContact', return_multiple=True, find_num=find_num)
    wxids = []
    for addr in addrs:
        array = ctypes.create_string_buffer(80)
        if ReadProcessMemory(h_process, void_p(addr - 30), array, 80, 0) == 0: return "None"
        array = bytes(array)  # .split(b"\\")[0]
        array = array.split(b"\\Msg")[0]
        array = array.split(b"\\")[-1]
        wxids.append(array.decode('utf-8', errors='ignore'))
    wxid = max(wxids, key=wxids.count) if wxids else "None"
    return wxid


def get_wx_dir(wxid):
    if not wxid:
        return ''
    try:
        is_w_dir = False
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "FileSavePath")
            winreg.CloseKey(key)
            w_dir = value
            is_w_dir = True
        except Exception as e:
            w_dir = "MyDocument:"

        if not is_w_dir:
            try:
                user_profile = os.environ.get("USERPROFILE")
                path_3ebffe94 = os.path.join(user_profile, "AppData", "Roaming", "Tencent", "WeChat", "All Users",
                                             "config",
                                             "3ebffe94.ini")
                with open(path_3ebffe94, "r", encoding="utf-8") as f:
                    w_dir = f.read()
                is_w_dir = True
            except Exception as e:
                w_dir = "MyDocument:"

        if w_dir == "MyDocument:":
            try:
                # 打开注册表路径
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
                documents_path = winreg.QueryValueEx(key, "Personal")[0]  # 读取文档实际目录路径
                winreg.CloseKey(key)  # 关闭注册表
                documents_paths = os.path.split(documents_path)
                if "%" in documents_paths[0]:
                    w_dir = os.environ.get(documents_paths[0].replace("%", ""))
                    w_dir = os.path.join(w_dir, os.path.join(*documents_paths[1:]))
                    # print(1, w_dir)
                else:
                    w_dir = documents_path
            except Exception as e:
                profile = os.environ.get("USERPROFILE")
                w_dir = os.path.join(profile, "Documents")
        msg_dir = os.path.join(w_dir, "WeChat Files", wxid)
        return msg_dir
    except FileNotFoundError:
        return ''


def get_key(db_path, addr_len):
    def read_key_bytes(h_process, address, address_len=8):
        array = ctypes.create_string_buffer(address_len)
        if ReadProcessMemory(h_process, void_p(address), array, address_len, 0) == 0: return ""
        address = int.from_bytes(array, byteorder='little')  # 逆序转换为int地址（key地址）
        key = ctypes.create_string_buffer(32)
        if ReadProcessMemory(h_process, void_p(address), key, 32, 0) == 0: return ""
        key_bytes = bytes(key)
        return key_bytes

    def verify_key(key, wx_db_path):
        if not wx_db_path:
            return True
        KEY_SIZE = 32
        DEFAULT_PAGESIZE = 4096
        DEFAULT_ITER = 64000
        with open(wx_db_path, "rb") as file:
            blist = file.read(5000)
        salt = blist[:16]
        byteKey = hashlib.pbkdf2_hmac("sha1", key, salt, DEFAULT_ITER, KEY_SIZE)
        first = blist[16:DEFAULT_PAGESIZE]

        mac_salt = bytes([(salt[i] ^ 58) for i in range(16)])
        mac_key = hashlib.pbkdf2_hmac("sha1", byteKey, mac_salt, 2, KEY_SIZE)
        hash_mac = hmac.new(mac_key, first[:-32], hashlib.sha1)
        hash_mac.update(b'\x01\x00\x00\x00')

        if hash_mac.digest() != first[-32:-12]:
            return False
        return True

    phone_type1 = "iphone\x00"
    phone_type2 = "android\x00"
    phone_type3 = "ipad\x00"

    pm = pymem.Pymem("WeChat.exe")
    module_name = "WeChatWin.dll"

    MicroMsg_path = os.path.join(db_path, "MSG", "MicroMsg.db")

    type1_addrs = pm.pattern_scan_module(phone_type1.encode(), module_name, return_multiple=True)
    type2_addrs = pm.pattern_scan_module(phone_type2.encode(), module_name, return_multiple=True)
    type3_addrs = pm.pattern_scan_module(phone_type3.encode(), module_name, return_multiple=True)
    type_addrs = type1_addrs if len(type1_addrs) >= 2 else type2_addrs if len(type2_addrs) >= 2 else type3_addrs if len(
        type3_addrs) >= 2 else ""
    # print(type_addrs)
    if type_addrs == "":
        return ""
    for i in type_addrs[::-1]:
        for j in range(i, i - 2000, -addr_len):
            key_bytes = read_key_bytes(pm.process_handle, j, addr_len)
            if key_bytes == "":
                continue
            if db_path != "" and verify_key(key_bytes, MicroMsg_path):
                return key_bytes.hex()
    return ""


def dump_wechat_info_v3(version_list, pid) -> WeChatInfo:
    wechat_info = WeChatInfo()
    wechat_info.pid = pid
    wechat_info.version = get_version(pid)
    process = psutil.Process(pid)
    pythoncom.CoInitialize()

    wechat_base_address = 0
    for module in process.memory_maps(grouped=False):
        if module.path and 'WeChatWin.dll' in module.path:
            wechat_base_address = int(module.addr, 16)
            break

    if wechat_base_address == 0:
        wechat_info.errmsg = '错误！请登录微信。'
        return wechat_info

    Handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, process.pid)

    bias_list = version_list.get(wechat_info.version)
    if not isinstance(bias_list, list) or len(bias_list) <= 4:
        wechat_info.errcode = 405
        wechat_info.errmsg = '错误！微信版本不匹配，请手动填写信息。'
        return wechat_info
    else:
        name_base_address = wechat_base_address + bias_list[0]
        account__base_address = wechat_base_address + bias_list[1]
        mobile_base_address = wechat_base_address + bias_list[2]

        wechat_info.account_name = get_info_without_key(Handle, account__base_address, 32) if bias_list[1] != 0 else "None"
        wechat_info.phone = get_info_without_key(Handle, mobile_base_address, 64) if bias_list[2] != 0 else "None"
        wechat_info.nick_name = get_info_without_key(Handle, name_base_address, 64) if bias_list[0] != 0 else "None"

    addrLen = get_exe_bit(process.exe()) // 8

    wechat_info.wxid = get_info_wxid(Handle)
    wechat_info.wx_dir = get_wx_dir(wechat_info.wxid)
    wechat_info.key = get_key(wechat_info.wx_dir, addrLen)
    if not wechat_info.key:
        wechat_info.errcode = 404
        wechat_info.errmsg = '请重启微信后重试。'
    else:
        wechat_info.errcode = 200
    return wechat_info

