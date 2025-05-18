#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/8 17:30 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-hardlink.py 
@Description : 
"""
import hashlib
import os
import traceback
from lxml import etree

from wxManager import Me
from wxManager.merge import increase_data
from wxManager.model.db_model import DataBaseBase
from wxManager.log import logger
from wxManager.model.message import Message
from wxManager.parser.util.protocbuf import file_info_pb2
from google.protobuf.json_format import MessageToJson, MessageToDict

image_root_path = "msg\\attach\\"
video_root_path = "msg\\video\\"
file_root_path = "msg\\file\\"


def get_md5_from_xml(content, type_="img"):
    if not content:
        return None
    try:
        content = content.strip('null:').strip().replace(' length="0" ', ' ')  # 哪个天才在xml里写两个一样的字段 length="0"
        # 解析XML
        parser = etree.XMLParser(recover=True)
        root = etree.fromstring(content, parser=parser)
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


class HardLinkDB(DataBaseBase):
    def get_image_path(self):
        pass

    def create_index(self):
        sql = "CREATE INDEX IF NOT EXISTS image_hardlink_info_v3_md5 ON image_hardlink_info_v3(md5);"
        try:
            cursor = self.DB.cursor()
            cursor.execute(sql)
            self.commit()
            cursor.close()
        except:
            pass

        sql = "CREATE INDEX IF NOT EXISTS video_hardlink_info_v3_md5 ON video_hardlink_info_v3(md5);"
        try:
            cursor = self.DB.cursor()
            cursor.execute(sql)
            self.commit()
            cursor.close()
        except:
            pass

        sql = "CREATE INDEX IF NOT EXISTS file_hardlink_info_v3_md5 ON file_hardlink_info_v3(md5);"
        try:
            cursor = self.DB.cursor()
            cursor.execute(sql)
            self.commit()
            cursor.close()
        except:
            pass

    def get_image_by_md5(self, md5: str):
        sql = '''
        select file_size,type,file_name,dir2id.username,dir2id2.username,_rowid_,modify_time,extra_buffer
        from image_hardlink_info_v3
        join dir2id on dir2id.rowid = dir1
        join dir2id as dir2id2 on dir2id2.rowid=dir2
        where md5=?
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql, [md5])
        result = cursor.fetchall()
        if result:
            return result[0]
        return None

    def get_video_by_md5(self, md5: str):
        sql = '''
        SELECT file_size, type, file_name, dir2id.username, dir2id2.username, _rowid_, modify_time, extra_buffer
        FROM video_hardlink_info_v3
        JOIN dir2id ON dir2id.rowid = dir1
        LEFT JOIN dir2id AS dir2id2 ON dir2id2.rowid = dir2 AND dir2 != 0
        WHERE md5 = ?
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql, [md5])
        result = cursor.fetchall()
        if result:
            return result[0]
        return None

    def get_file_by_md5(self, md5: str):
        sql = '''
        select file_size,type,file_name,dir2id.username,dir2id2.username,_rowid_,modify_time,extra_buffer
        from file_hardlink_info_v3
        join dir2id on dir2id.rowid = dir1
        LEFT JOIN dir2id AS dir2id2 ON dir2id2.rowid = dir2 AND dir2 != 0
        where md5=?
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql, [md5])
        result = cursor.fetchall()
        if result:
            return result[0]
        return None

    def get_video(self, md5, thumb=False):
        video_info = self.get_video_by_md5(md5)
        if video_info:
            type_ = video_info[1]
            if type_ == 5:
                dir1 = video_info[3]
                dir2 = video_info[4]
                extra_buffer = video_info[7]
                # 创建顶级消息对象
                message = file_info_pb2.FileInfoData()
                # 解析二进制数据
                message.ParseFromString(extra_buffer)
                extra_dic = MessageToDict(message)
                dir3 = extra_dic.get('dir3', '')
                file_name = video_info[2]
                result = os.path.join(video_root_path, dir1, dir2, 'Rec', dir3, 'V', file_name)
            else:
                dir1 = video_info[3]
                data_image = video_info[2].split('.')[0] + '_thumb.jpg' if thumb else video_info[2]
                dat_image = os.path.join(video_root_path, dir1, data_image)
                result = dat_image
            return result
        return ''

    def get_image_thumb(self, message: Message, talker_username):
        """
        @param message:
        @param talker_username: 聊天对象的wxid
        @return:
        """
        dir1 = hashlib.md5(talker_username.encode('utf-8')).hexdigest()
        str_time = message.str_time
        dir2 = str_time[:7]  # 2024-12
        dir0 = "Img"
        local_id = message.local_id
        create_time = message.timestamp
        data_image = f'{message.file_name}_t.dat' if message.file_name else f'{local_id}_{create_time}_t.dat'
        return os.path.join(image_root_path, dir1, dir2, dir0, data_image)

    def get_image_by_time(self, message: Message, talker_username):
        """
        @param message:
        @param talker_username: 聊天对象的wxid
        @return:
        """
        dir1 = hashlib.md5(talker_username.encode('utf-8')).hexdigest()
        str_time = message.str_time
        dir2 = str_time[:7]  # 2024-12
        dir0 = "Img"
        local_id = message.local_id
        create_time = message.timestamp
        data_image = f'{message.file_name}_W.dat' if message.file_name else f'{local_id}_{create_time}_W.dat'
        path1 = os.path.join(image_root_path, dir1, dir2, dir0, data_image)
        if os.path.exists(os.path.join(Me().wx_dir, path1)):
            return path1
        else:
            data_image = f'{message.file_name}_h.dat' if message.file_name else f'{local_id}_{create_time}_h.dat'
            path1 = os.path.join(image_root_path, dir1, dir2, dir0, data_image)
            if os.path.exists(os.path.join(Me().wx_dir, path1)):
                return path1
            data_image = f'{message.file_name}.dat' if message.file_name else f'{local_id}_{create_time}.dat'
            path1 = os.path.join(image_root_path, dir1, dir2, dir0, data_image)
            return path1

    def get_image(self, content, message, up_dir="", md5=None, thumb=False, talker_username='') -> str:
        """
        @param content: image xml
        @param message:
        @param up_dir:
        @param md5: image的md5
        @param thumb: 是否是缩略图
        @param talker_username: 聊天对象的wxid
        @return:
        """
        result = '.'
        self.create_index()
        if thumb:
            return self.get_image_thumb(message, talker_username)
        else:
            result = self.get_image_by_time(message, talker_username)
            if os.path.exists(os.path.join(Me().wx_dir, result)):
                return result
        if not md5:
            md5 = get_md5_from_xml(content)
        if md5:
            imginfo = self.get_image_by_md5(md5)
            if imginfo:
                type_ = imginfo[1]
                if type_ == 4:
                    dir1 = imginfo[3]
                    dir2 = imginfo[4]
                    extra_buffer = imginfo[7]
                    # 创建顶级消息对象
                    message = file_info_pb2.FileInfoData()
                    # 解析二进制数据
                    message.ParseFromString(extra_buffer)
                    extra_dic = MessageToDict(message)
                    dir3 = extra_dic.get('dir3', '')
                    file_name = imginfo[2]
                    result = os.path.join(image_root_path, dir1, dir2, 'Rec', dir3, 'Img', file_name)
                else:
                    dir1 = imginfo[3]
                    dir2 = imginfo[4]
                    data_image = imginfo[2]
                    dir0 = "Img"
                    dat_image = os.path.join(image_root_path, dir1, dir2, dir0, data_image)
                    result = dat_image
            else:
                result = self.get_image_thumb(message, talker_username)
        else:
            result = self.get_image_by_time(message, talker_username)
        return result

    def get_file(self, md5):
        file_info = self.get_file_by_md5(md5)
        if file_info:
            type_ = file_info[1]
            if type_ == 6:
                dir1 = file_info[3]
                dir2 = file_info[4]
                extra_buffer = file_info[7]
                # 创建顶级消息对象
                message = file_info_pb2.FileInfoData()
                # 解析二进制数据
                message.ParseFromString(extra_buffer)
                extra_dic = MessageToDict(message)
                dir3 = extra_dic.get('dir3', '')
                file_name = file_info[2]
                filepath = os.path.join(image_root_path, dir1, dir2, dir3, file_name)
            else:
                dir1 = file_info[3]
                filename = file_info[2]
                filepath = os.path.join(file_root_path, dir1, filename)
            return filepath
        return ''

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_data(db_path, self.cursor, self.DB, 'file_hardlink_info_v3', 'md5', exclude_column='_rowid_')
            increase_data(db_path, self.cursor, self.DB, 'image_hardlink_info_v3', 'md5', exclude_column='_rowid_')
            increase_data(db_path, self.cursor, self.DB, 'video_hardlink_info_v3', 'md5', exclude_column='_rowid_')
            increase_data(db_path, self.cursor, self.DB, 'dir2id', 'username')
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()


if __name__ == '__main__':
    pass
