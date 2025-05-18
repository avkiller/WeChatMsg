#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2025/2/17 21:43 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-open_im_msg.py 
@Description : 
"""

import os.path
import sqlite3
import threading
import traceback
import concurrent
import hashlib
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from typing import Tuple

from wxManager import MessageType
from wxManager.merge import increase_data, increase_update_data
from wxManager.log import logger
from wxManager.model import DataBaseBase
from wxManager.parser.util.protocbuf.msg_pb2 import MessageBytesExtra


def convert_to_timestamp_(time_input) -> int:
    if isinstance(time_input, (int, float)):
        # 如果输入是时间戳，直接返回
        return int(time_input)
    elif isinstance(time_input, str):
        # 如果输入是格式化的时间字符串，将其转换为时间戳
        try:
            dt_object = datetime.strptime(time_input, '%Y-%m-%d %H:%M:%S')
            return int(dt_object.timestamp())
        except ValueError:
            # 如果转换失败，可能是其他格式的字符串，可以根据需要添加更多的处理逻辑
            print("Error: Unsupported date format")
            return -1
    elif isinstance(time_input, date):
        # 如果输入是datetime.date对象，将其转换为时间戳
        dt_object = datetime.combine(time_input, datetime.min.time())
        return int(dt_object.timestamp())
    else:
        print("Error: Unsupported input type")
        return -1


def convert_to_timestamp(time_range) -> Tuple[int, int]:
    """
    将时间转换成时间戳
    @param time_range:
    @return:
    """
    if not time_range:
        return 0, 0
    else:
        return convert_to_timestamp_(time_range[0]), convert_to_timestamp_(time_range[1])


def get_local_type(type_: MessageType):
    type_name_dict = {
        MessageType.Text: (1, 0),
        MessageType.Image: (3, 0),
        MessageType.Audio: (34, 0),
        MessageType.Video: (43, 0),
        MessageType.Emoji: (47, 0),
        MessageType.BusinessCard: (42, 0),
        MessageType.OpenIMBCard: (66, 0),
        MessageType.Position: (48, 0),
        MessageType.FavNote: (49, 40),
        MessageType.FavNote: (49, 24),
        (49, 53): "接龙",
        MessageType.File: (49, 0),
        MessageType.Text2: (49, 1),
        MessageType.Music: (49, 3),
        MessageType.Music: (49, 76),
        MessageType.LinkMessage: (49, 5),
        MessageType.File: (49, 6),
        (49, 8): "用户上传的GIF表情",
        MessageType.System: (49, 17),  # 发起了位置共享
        MessageType.MergedMessages: (49, 19),
        MessageType.Applet: (49, 33),
        MessageType.Applet2: (49, 36),
        MessageType.WeChatVideo: (49, 51),
        (49, 57): MessageType.Quote,
        (49, 63): "视频号直播或直播回放等",
        (49, 87): "群公告",
        (49, 88): "视频号直播或直播回放等",
        (49, 2000): MessageType.Transfer,
        (49, 2003): "赠送红包封面",
        (50, 0): MessageType.Voip,
        (10000, 0): MessageType.System,
        (10000, 4): MessageType.Pat,
        (10000, 8000): MessageType.System
    }
    return type_name_dict.get(type_, (0, 0))


class OpenIMMsgDB(DataBaseBase):

    def _get_messages_by_num(self, cursor, username_, start_sort_seq, msg_num):
        """

        @param cursor:
        @param username_:
        @param start_sort_seq:
        @param msg_num:
        @return:
        """
        sql = '''
        select localId,TalkerId,Type,statusEx,IsSender,CreateTime,Status,StrContent,strftime('%Y-%m-%d %H:%M:%S',CreateTime,'unixepoch','localtime') as StrTime,MsgSvrID,BytesExtra,'',Reserved1
        from ChatCRMsg
        where StrTalker = ? and CreateTime < ?
        order by CreateTime desc 
        limit ?
        '''
        cursor.execute(sql, [username_, start_sort_seq, msg_num])
        result = cursor.fetchall()
        if result:
            return result
        else:
            return []

    def get_messages_by_num(self, username, start_sort_seq, msg_num=20):
        results = [self._get_messages_by_num(self.DB.cursor(), username, start_sort_seq, msg_num)]
        self.commit()
        return results

    def _get_messages_by_username(self, cursor, username: str,
                                  time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        if time_range:
            start_time, end_time = convert_to_timestamp(time_range)
        sql = f'''
        select localId,TalkerId,Type,statusEx,IsSender,CreateTime,Status,StrContent,strftime('%Y-%m-%d %H:%M:%S',CreateTime,'unixepoch','localtime') as StrTime,MsgSvrID,BytesExtra,'',Reserved1
        from ChatCRMsg
        where StrTalker=?
        {'AND CreateTime>' + str(start_time) + ' AND CreateTime<' + str(end_time) if time_range else ''}
        order by CreateTime
        '''
        cursor.execute(sql, [username])
        result = cursor.fetchall()
        if result:
            return result
        else:
            return []

    def get_messages_by_username(self, username: str,
                                 time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        return self._get_messages_by_username(self.DB.cursor(), username, time_range)

    def get_message_by_server_id(self, username, server_id):
        """
        获取小于start_sort_seq的msg_num个消息
        @param username:
        @param server_id:
        @return: messages, 最后一条消息的start_sort_seq
        """
        sql = f'''
    select localId,TalkerId,Type,statusEx,IsSender,CreateTime,Status,StrContent,strftime('%Y-%m-%d %H:%M:%S',CreateTime,'unixepoch','localtime') as StrTime,MsgSvrID,BytesExtra,'',Reserved1
    from ChatCRMsg
    where MsgSvrID=?
'''
        for db in self.DB:
            cursor = db.cursor()
            cursor.execute(sql, [server_id])
            result = cursor.fetchone()
            if result:
                return result

        return None

    def _get_messages_by_type(self, cursor, username: str, type_: MessageType,
                              time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        if time_range:
            start_time, end_time = convert_to_timestamp(time_range)
        local_type, sub_type = get_local_type(type_)
        sql = f'''
            select localId,TalkerId,Type,SubType,IsSender,CreateTime,Status,StrContent,strftime('%Y-%m-%d %H:%M:%S',CreateTime,'unixepoch','localtime') as StrTime,MsgSvrID,BytesExtra,CompressContent,DisplayContent
            from MSG
            where StrTalker=? and Type=? and SubType = ?
            {'AND CreateTime>' + str(start_time) + ' AND CreateTime<' + str(end_time) if time_range else ''}
            order by CreateTime
        '''
        cursor.execute(sql, [username, local_type, sub_type])
        result = cursor.fetchall()
        if result:
            return result
        else:
            return None

    def get_messages_by_type(self, username: str, type_: MessageType,
                             time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        return self._get_messages_by_type(self.DB.cursor, username, type_, time_range)

    def _get_messages_calendar(self, cursor, username):
        """
        获取某个人的聊天日历列表
        @param username_:
        @return:
        """
        sql = f'''SELECT DISTINCT strftime('%Y-%m-%d',CreateTime,'unixepoch','localtime') AS date
            from PublicMsg
            where StrTalker=?
            ORDER BY date desc;
        '''
        cursor.execute(sql, [username])
        result = cursor.fetchall()
        return (data[0] for data in result)

    def get_messages_calendar(self, username):
        res = []
        r1 = self._get_messages_calendar(self.DB.cursor(), username)
        if r1:
            res.extend(r1)
        res.sort()
        return res

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_data(db_path, self.cursor, self.DB, 'ChatCRMsg', 'MsgSvrID', 1, exclude_column='localId')
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()
