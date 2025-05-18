#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2025/2/4 1:26 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : wxManager-hard_link_image.py 
@Description : 
"""
import binascii
import hashlib
import os
import traceback
import xml.etree.ElementTree as ET

from wxManager.merge import increase_data
from wxManager.model.db_model import DataBaseBase
from wxManager.log import logger
from wxManager.model.message import Message
from wxManager.parser.util.protocbuf.msg_pb2 import MessageBytesExtra

image_root_path = "FileStorage\\MsgAttach\\"


def get_md5_from_xml(content, type_="img"):
    try:
        if not content:
            return None
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
    except:
        logger.error(traceback.format_exc())
        logger.error(content)
        return None


class HardLinkImage(DataBaseBase):
    def get_image_path(self):
        pass

    def get_image_by_md5(self, md5: bytes | str):
        if not md5:
            return None
        if not self.open_flag:
            return None
        if isinstance(md5, str):
            md5 = binascii.unhexlify(md5)
        sql = """
            select Md5Hash,MD5,FileName,HardLinkImageID.Dir as DirName1,HardLinkImageID2.Dir as DirName2
            from HardLinkImageAttribute
            join HardLinkImageID on HardLinkImageAttribute.DirID1 = HardLinkImageID.DirID
            join HardLinkImageID as HardLinkImageID2 on HardLinkImageAttribute.DirID2 = HardLinkImageID2.DirID
            where MD5 = ?;
        """
        cursor = self.DB.cursor()
        try:
            cursor.execute(sql, [md5])
        except AttributeError:
            self.init_database()
            cursor.execute(sql, [md5])
        result = cursor.fetchone()
        return result

    def get_image_original(self, content, bytesExtra) -> str:
        msg_bytes = MessageBytesExtra()
        msg_bytes.ParseFromString(bytesExtra)
        result = ''
        for tmp in msg_bytes.message2:
            if tmp.field1 != 4:
                continue
            pathh = tmp.field2  # wxid\FileStorage\...
            pathh = "\\".join(pathh.split("\\")[1:])
            return pathh
        md5 = get_md5_from_xml(content)
        if not md5:
            pass
        else:
            result = self.get_image_by_md5(binascii.unhexlify(md5))
            if result:
                dir1 = result[3]
                dir2 = result[4]
                data_image = result[2]
                dir0 = "Image"
                dat_image = os.path.join(image_root_path, dir1, dir0, dir2, data_image)
                result = dat_image
        return result

    def get_image_thumb(self, content, bytesExtra) -> str:
        msg_bytes = MessageBytesExtra()
        msg_bytes.ParseFromString(bytesExtra)
        result = ''
        for tmp in msg_bytes.message2:
            if tmp.field1 != 3:
                continue
            pathh = tmp.field2  # wxid\FileStorage\...
            pathh = "\\".join(pathh.split("\\")[1:])
            return pathh
        md5 = get_md5_from_xml(content)
        if not md5:
            pass
        else:
            result = self.get_image_by_md5(md5)
            if result:
                dir1 = result[3]
                dir2 = result[4]
                data_image = result[2]
                dir0 = "Thumb"
                dat_image = os.path.join(image_root_path, dir1, dir0, dir2, data_image)
                result = dat_image
        return result

    def get_image(self, content, bytesExtra, up_dir="", md5=None, thumb=False) -> str:
        result = '.'
        if md5:
            imginfo = self.get_image_by_md5(md5)
            if imginfo:
                dir1 = imginfo[3]
                dir2 = imginfo[4]
                data_image = imginfo[2]
                dir0 = "Thumb"
                dat_image = os.path.join(image_root_path, dir1, dir0, dir2, data_image)
                result = dat_image
        else:
            if thumb:
                result = self.get_image_thumb(content, bytesExtra)
            else:
                result = self.get_image_original(content, bytesExtra)
                if not result:
                    result = self.get_image_thumb(content, bytesExtra)
        return result

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_data(db_path, self.cursor, self.DB, 'HardLinkImageAttribute', 'Md5Hash', 0)
            increase_data(db_path, self.cursor, self.DB, 'HardLinkImageID', 'DirId', 0)
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()


if __name__ == '__main__':
    pass
