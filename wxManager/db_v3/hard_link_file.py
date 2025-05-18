#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2025/2/4 1:38 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : wxManager-hard_link_file.py 
@Description : 
"""

import binascii
import hashlib
import os
import sqlite3
import traceback
import xml.etree.ElementTree as ET

from wxManager.merge import increase_data
from wxManager.model.db_model import DataBaseBase
from wxManager.log import logger

file_root_path = "FileStorage\\File\\"


def get_md5_from_xml(content, type_="img"):
    try:
        content = content.strip('null:').strip()
        # 解析XML
        root = ET.fromstring(content)
        if type_ == "img":
            # 提取md5的值
            md5_value = root.find(".//img").get("md5")
        elif type_ == "video":
            md5_value = root.find(".//videomsg").get("md5")
        else:
            md5_value = None
        # print(md5_value)
        return md5_value
    except ET.ParseError:
        logger.error(traceback.format_exc())
        logger.error(content)
        return None


class HardLinkFile(DataBaseBase):
    def get_file_by_md5(self, md5: bytes | str):
        if not md5:
            return None
        if not self.open_flag:
            return None
        if isinstance(md5, str):
            md5 = binascii.unhexlify(md5)
        sql = """
            select Md5Hash,MD5,FileName,HardLinkFileID2.Dir as DirName2
            from HardLinkFileAttribute
            join HardLinkFileID as HardLinkFileID2 on HardLinkFileAttribute.DirID2 = HardLinkFileID2.DirID
            where MD5 = ?;
            """
        cursor = self.DB.cursor()
        try:
            cursor.execute(sql, [md5])
        except sqlite3.OperationalError:
            return None
        result = cursor.fetchone()
        return result

    def get_file(self, md5: bytes | str) -> str:
        file_path = ''
        file_info = self.get_file_by_md5(md5)
        if file_info:
            file_path = os.path.join(file_root_path, file_info[3], file_info[2])
        return file_path

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_data(db_path, self.cursor, self.DB, 'HardLinkFileAttribute', 'Md5Hash', 0)
            increase_data(db_path, self.cursor, self.DB, 'HardLinkFileID', 'DirId', 0)
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()


if __name__ == '__main__':
    pass
