import concurrent
import os.path
import shutil
import sqlite3
import threading
import traceback
from datetime import date
from typing import Tuple
from concurrent.futures import ThreadPoolExecutor

from wxManager import MessageType
from wxManager.merge import increase_data
from wxManager.db_v3.msg import convert_to_timestamp,get_local_type
from wxManager.model import DataBaseBase


class PublicMsg(DataBaseBase):

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

    def get_sport_score_by_name(self, username,
                                time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        if not self.open_flag:
            return 0

    def _get_messages_by_num(self, cursor, username_, start_sort_seq, msg_num):
        sql = '''
            select localId,TalkerId,Type,SubType,IsSender,CreateTime,Status,StrContent,strftime('%Y-%m-%d %H:%M:%S',CreateTime,'unixepoch','localtime') as StrTime,MsgSvrID,BytesExtra,CompressContent,DisplayContent
            from PublicMsg
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
        cursor = self.DB.cursor()
        yield self._get_messages_by_num(cursor, username, start_sort_seq, msg_num)

    def _get_messages_by_username(self, cursor, username: str,
                                  time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        if time_range:
            start_time, end_time = convert_to_timestamp(time_range)
        sql = f'''
            select localId,TalkerId,Type,SubType,IsSender,CreateTime,Status,StrContent,strftime('%Y-%m-%d %H:%M:%S',CreateTime,'unixepoch','localtime') as StrTime,MsgSvrID,BytesExtra,CompressContent,DisplayContent
            from PublicMsg
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
        select localId,TalkerId,Type,SubType,IsSender,CreateTime,Status,StrContent,strftime('%Y-%m-%d %H:%M:%S',CreateTime,'unixepoch','localtime') as StrTime,MsgSvrID,BytesExtra,CompressContent,DisplayContent
        from PublicMsg
        where MsgSvrID=?
    '''
        cursor = self.DB.cursor()
        cursor.execute(sql, [server_id])
        result = cursor.fetchone()
        if result:
            return result
        return None

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
            increase_data(db_path, self.cursor, self.DB, 'PublicMsg', 'MsgSvrID', 1, exclude_column='localId')
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()


if __name__ == '__main__':
    pdb = PublicMsg()
    db_path = "./Msg/PublicMsg.db"
    pdb.init_database()
    pdb.get_public_msg()
