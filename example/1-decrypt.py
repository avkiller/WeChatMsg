#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2025/3/11 20:27
@Author      : SiYuan
@Email       : 863909694@qq.com
@File        : wxManager-1-decrypt.py
@Description :
"""

import json
import os
from multiprocessing import freeze_support

from wxManager import Me
from wxManager.decrypt import get_info_v4, get_info_v3
from wxManager.decrypt.decrypt_dat import get_decode_code_v4
from wxManager.decrypt import decrypt_v4, decrypt_v3


def dump_v3():
    """
    解析微信3.x版本的数据库
    """
    version_list_path = '../wxManager/decrypt/version_list.json'
    with open(version_list_path, "r", encoding="utf-8") as f:
        version_list = json.loads(f.read())
    r_3 = get_info_v3(version_list)  # 微信3.x
    for wx_info in r_3:
        print(wx_info)
        me = Me()
        me.wx_dir = wx_info.wx_dir
        me.wxid = wx_info.wxid
        me.name = wx_info.nick_name
        info_data = me.to_json()
        output_dir = wx_info.wxid
        key = wx_info.key
        if not key:
            print('error! 未找到key，请重启微信后再试')
            continue
        wx_dir = wx_info.wx_dir
        decrypt_v3.decrypt_db_files(key, src_dir=wx_dir, dest_dir=output_dir)
        # 导出的数据库在 output_dir/Msg 文件夹下，后面会用到
        with open(os.path.join(output_dir, 'Msg', 'info.json'), 'w', encoding='utf-8') as f:
            json.dump(info_data, f, ensure_ascii=False, indent=4)
        print(f'数据库解析成功，在{os.path.join(output_dir, "Msg")}路径下')


def dump_v4():
    """
    解析微信4.0版本的数据库
    """
    r_4 = get_info_v4()  # 微信4.0
    for wx_info in r_4:
        print(wx_info)
        me = Me()
        me.wx_dir = wx_info.wx_dir
        me.wxid = wx_info.wxid
        me.name = wx_info.nick_name
        me.xor_key = get_decode_code_v4(wx_info.wx_dir)
        info_data = me.to_json()
        output_dir = wx_info.wxid  # 数据库输出文件夹
        key = wx_info.key
        if not key:
            print('error! 未找到key，请重启微信后再试')
            continue
        wx_dir = wx_info.wx_dir
        decrypt_v4.decrypt_db_files(key, src_dir=wx_dir, dest_dir=output_dir)
        # 导出的数据库在 output_dir/db_storage 文件夹下，后面会用到
        with open(os.path.join(output_dir, 'db_storage', 'info.json'), 'w', encoding='utf-8') as f:
            json.dump(info_data, f, ensure_ascii=False, indent=4)
        print(f'数据库解析成功，在{os.path.join(output_dir, "Msg")}路径下')


if __name__ == '__main__':
    freeze_support()  # 使用多进程必须
    # 根据自己的微信版本选择使用对应的函数
    dump_v3()  # 微信3.x
    # dump_v4() # 微信4.0
