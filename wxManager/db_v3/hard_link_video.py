#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2025/2/4 1:41 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : wxManager-hard_link_video.py 
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
from wxManager.parser.util.protocbuf.msg_pb2 import MessageBytesExtra

video_root_path = "FileStorage\\Video\\"


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


class HardLinkVideo(DataBaseBase):
    def get_video_by_md5(self, md5: bytes | str):
        if not md5:
            return None
        if not self.open_flag:
            return None
        if isinstance(md5, str):
            md5 = binascii.unhexlify(md5)
        sql = """
            select Md5Hash,MD5,FileName,HardLinkVideoID2.Dir as DirName2
            from HardLinkVideoAttribute
            join HardLinkVideoID as HardLinkVideoID2 on HardLinkVideoAttribute.DirID2 = HardLinkVideoID2.DirID
            where MD5 = ?;
            """
        cursor = self.DB.cursor()
        try:
            cursor.execute(sql, [md5])
        except sqlite3.OperationalError:
            return None
        result = cursor.fetchone()
        return result

    def get_video(self, content, bytesExtra, md5=None, thumb=False):
        if md5:
            result = self.get_video_by_md5(binascii.unhexlify(md5))
            if result:
                dir2 = result[3]
                data_image = result[2].split(".")[0] + ".jpg" if thumb else result[2]
                # dir0 = 'Thumb' if thumb else 'Image'
                dat_image = os.path.join(video_root_path, dir2, data_image)
                return dat_image
            else:
                return ''
        else:
            if bytesExtra:
                msg_bytes = MessageBytesExtra()
                msg_bytes.ParseFromString(bytesExtra)
                for tmp in msg_bytes.message2:
                    if tmp.field1 != (3 if thumb else 4):
                        continue
                    pathh = tmp.field2  # wxid\FileStorage\...
                    pathh = "\\".join(pathh.split("\\")[1:])
                    return pathh
                md5 = get_md5_from_xml(content, type_="video")
                if not md5:
                    return ''
                result = self.get_video_by_md5(binascii.unhexlify(md5))
                if result:
                    dir2 = result[3]
                    data_image = result[2].split(".")[0] + ".jpg" if thumb else result[2]
                    # dir0 = 'Thumb' if thumb else 'Image'
                    dat_image = os.path.join(video_root_path, dir2, data_image)
                    return dat_image
                else:
                    return ''
            else:
                return ''

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_data(db_path, self.cursor, self.DB, 'HardLinkVideoAttribute', 'Md5Hash', 0)
            increase_data(db_path, self.cursor, self.DB, 'HardLinkVideoID', 'DirId', 0)
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()


if __name__ == '__main__':
    pass
