import os.path
import sqlite3
import threading
from datetime import date
from typing import Tuple

from wxManager.db_v3.msg import convert_to_timestamp

lock = threading.Lock()
DB = None
cursor = None
db_path = '.'

# db_path = "./app/Database/Msg/Misc.db"


# db_path = './Msg/Misc.db'
# 朋友圈类型
type_ = {
    '1': '图文',
    '2': '文本',
    '3': '应用分享(如：网易云音乐)',
    '15': '视频',
    '28': '视频号'
}


def singleton(cls):
    _instance = {}

    def inner():
        if cls not in _instance:
            _instance[cls] = cls()
        return _instance[cls]

    return inner


# @singleton
class Sns:
    def __init__(self):
        self.DB = None
        self.cursor = None
        self.open_flag = False
        self.init_database()

    def init_database(self, db_dir=''):
        global db_path
        if not self.open_flag:
            if db_dir:
                db_path = os.path.join(db_dir, 'Sns.db')
            if os.path.exists(db_path):
                self.DB = sqlite3.connect(db_path, check_same_thread=False)
                # '''创建游标'''
                self.cursor = self.DB.cursor()
                self.open_flag = True
                if lock.locked():
                    lock.release()

    def close(self):
        if self.open_flag:
            try:
                lock.acquire(True)
                self.open_flag = False
                self.DB.close()
            finally:
                lock.release()

    def get_sns_bg_url(self) -> str:
        """
        获取朋友圈背景URL
        @return:
        """
        sql = '''
            select StrValue
            from SnsConfigV20
            where Key=6;
        '''
        try:
            lock.acquire(True)
            self.cursor.execute(sql)
            result = self.cursor.fetchall()
            if result:
                return result[0][0]
        finally:
            lock.release()
        return ''

    def get_feeds(
            self,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ):
        """

        @param time_range:
        @return: List[
            a[0]:FeedId,
            a[1]:CreateTime,时间戳
            a[2]:StrTime,时间戳,
            a[3]:Type,类型,
            a[4]:UserName,用户名wxid,
            a[5]:Status,状态,
            a[6]:StringId,id,
            a[7]:Content,xml,
        ]
        """
        if not self.open_flag:
            return None
        if time_range:
            start_time, end_time = convert_to_timestamp(time_range)
        result = []
        sql = f'''
                select FeedId,CreateTime,strftime('%Y-%m-%d %H:%M:%S',CreateTime,'unixepoch','localtime') as StrTime,Type,UserName,Status,StringId,Content
                from FeedsV20
                {'where  CreateTime>' + str(start_time) + ' AND CreateTime<' + str(end_time) if time_range else ''}
                order by CreateTime
            '''
        try:
            lock.acquire(True)
            self.cursor.execute(sql)
            result = self.cursor.fetchall()
        finally:
            lock.release()
        return result

    def get_feeds_by_username(
            self,
            username,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ):
        """
        @param time_range:
        @return: List[
            a[0]:FeedId,
            a[1]:CreateTime,时间戳
            a[2]:StrTime,时间戳,
            a[3]:Type,类型,
            a[4]:UserName,用户名wxid,
            a[5]:Status,状态,
            a[6]:StringId,id,
            a[7]:Content,xml,
        ]
        """
        if not self.open_flag:
            return []
        if time_range:
            start_time, end_time = convert_to_timestamp(time_range)
        result = []
        sql = f'''
                select FeedId,CreateTime,strftime('%Y-%m-%d %H:%M:%S',CreateTime,'unixepoch','localtime') as StrTime,Type,UserName,Status,StringId,Content
                from FeedsV20
                where UserName=?
                {' AND CreateTime > ' + str(start_time) + ' AND CreateTime < ' + str(end_time) if time_range else ''} 
                order by CreateTime
            '''
        try:
            lock.acquire(True)
            self.cursor.execute(sql, [username])
            result = self.cursor.fetchall()
        finally:
            lock.release()
        return result

    def get_comment(self, feed_id):
        """

        @param feed_id:
        @return: List[
            a[0]:FeedId,
            a[1]:CommentId,
            a[2]:CreateTime,时间戳,
            a[3]:StrTime,
            a[4]:CommentType,用户名wxid,
            a[5]:Content,
            a[6]:FromUserName
            a[7]:ReplyUserName
            a[8]:ReplyId
        ]
        """
        if not self.open_flag:
            return []

        result = []
        sql = f'''
                select FeedId,CommentId,CreateTime,strftime('%Y-%m-%d %H:%M:%S',CreateTime,'unixepoch','localtime') as StrTime,CommentType,Content,FromUserName,ReplyUserName,ReplyId
                from CommentV20
                where FeedId=?
            '''
        try:
            lock.acquire(True)
            self.cursor.execute(sql, [feed_id])
            result = self.cursor.fetchall()
        finally:
            lock.release()
        return result

    def __del__(self):
        self.close()