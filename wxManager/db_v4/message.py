#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/6 23:07 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-message.py 
@Description : 
"""
import concurrent
import hashlib
import os
import shutil
import sqlite3
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from typing import Tuple

from wxManager import MessageType
from wxManager.merge import increase_data, increase_update_data
from wxManager.model.db_model import DataBaseBase


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
    return type_


class MessageDB(DataBaseBase):
    columns = (
        "local_id,server_id,local_type,sort_seq,Name2Id.user_name as sender_username,create_time,strftime('%Y-%m-%d %H:%M:%S',"
        "create_time,'unixepoch','localtime') as StrTime,status,upload_status,server_seq,origin_source,source,"
        "message_content,compress_content,packed_info_data")

    def get_messages(self):
        pass

    def table_exists(self, cursor, table_name):
        # 查询 sqlite_master 系统表，判断表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        result = cursor.fetchone()
        # 如果结果不为空，表存在；否则表不存在
        return result

    def _get_messages_by_username(self, cursor, username: str,
                                  time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        table_name = f'Msg_{hashlib.md5(username.encode("utf-8")).hexdigest()}'
        if not self.table_exists(cursor, table_name):
            return None
        if time_range:
            start_time, end_time = convert_to_timestamp(time_range)
        sql = f'''
select {MessageDB.columns}
from {table_name} as msg
join Name2Id on msg.real_sender_id = Name2Id.rowid
{'where create_time>' + str(start_time) + ' AND create_time<' + str(end_time) if time_range else ''}
order by sort_seq
        '''
        cursor.execute(sql)
        result = cursor.fetchall()
        if result:
            return result
        else:
            return None

    def get_messages_by_username(self, username: str,
                                 time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # 创建一个任务列表
            futures = [
                executor.submit(self._get_messages_by_username, db.cursor(), username, time_range)
                for db in self.DB
            ]

            # 等待所有任务完成，并获取结果
            results = []
            for future in concurrent.futures.as_completed(futures):
                r1 = future.result()
                if r1:
                    # results.append(future.result())
                    results.extend(r1)

        return results
        results = []
        # for db in self.DB:
        #     cursor = db.cursor()
        #     yield self._get_messages_by_num(cursor, username, start_sort_seq, msg_num)
        lock = threading.Lock()  # 锁，用于确保线程安全地写入 results

        def task(db):
            """
            每个线程执行的任务，获取某个数据库实例中的查询结果。
            """
            cursor = db.cursor()
            try:
                data = self._get_messages_by_username(cursor, username, time_range)
                with lock:  # 确保对 results 的操作是线程安全的
                    results.append(data)
            finally:
                cursor.close()

        # 使用线程池
        with ThreadPoolExecutor(max_workers=len(self.DB)) as executor:
            executor.map(task, self.DB)
        self.commit()
        return results

    def _get_messages_by_num(self, cursor, username, start_sort_seq, msg_num):
        table_name = f'Msg_{hashlib.md5(username.encode("utf-8")).hexdigest()}'
        if not self.table_exists(cursor, table_name):
            return []
        sql = f'''
        select {MessageDB.columns}
        from {table_name} as msg
        join Name2Id on msg.real_sender_id = Name2Id.rowid
        where sort_seq < ?
        order by sort_seq desc 
        limit ?
                '''
        cursor.execute(sql, [start_sort_seq, msg_num])
        result = cursor.fetchall()
        if result:
            return result
        else:
            return []

    def get_message_by_server_id(self, username, server_id):
        """
        获取小于start_sort_seq的msg_num个消息
        @param username:
        @param server_id:
        @return: messages, 最后一条消息的start_sort_seq
        """
        table_name = f'Msg_{hashlib.md5(username.encode("utf-8")).hexdigest()}'
        sql = f'''
select {MessageDB.columns}
from {table_name} as msg
join Name2Id on msg.real_sender_id = Name2Id.rowid
where server_id = ?
'''
        for db in self.DB:
            cursor = db.cursor()
            if not self.table_exists(cursor, table_name):
                continue
            cursor.execute(sql, [server_id])
            result = cursor.fetchone()
            if result:
                return result

    def get_messages_by_num(self, username, start_sort_seq, msg_num=20):
        results = []
        # for db in self.DB:
        #     cursor = db.cursor()
        #     yield self._get_messages_by_num(cursor, username, start_sort_seq, msg_num)
        lock = threading.Lock()  # 锁，用于确保线程安全地写入 results

        def task(db):
            """
            每个线程执行的任务，获取某个数据库实例中的查询结果。
            """
            cursor = db.cursor()
            try:
                data = self._get_messages_by_num(cursor, username, start_sort_seq, msg_num)
                with lock:  # 确保对 results 的操作是线程安全的
                    results.append(data)
            finally:
                cursor.close()

        # 使用线程池
        with ThreadPoolExecutor(max_workers=len(self.DB)) as executor:
            executor.map(task, self.DB)
        self.commit()
        return results

    def _get_messages_calendar(self, cursor, username):
        """
        获取某个人的聊天日历列表
        @param username_:
        @return:
        """
        table_name = f'Msg_{hashlib.md5(username.encode("utf-8")).hexdigest()}'
        if not self.table_exists(cursor, table_name):
            return None
        sql = f'''SELECT DISTINCT strftime('%Y-%m-%d',create_time,'unixepoch','localtime') AS date
            from {table_name} as msg
            ORDER BY date desc;
        '''
        cursor.execute(sql)
        result = cursor.fetchall()
        return (data[0] for data in result)

    def get_messages_calendar(self, username):
        res = []
        for db in self.DB:
            r1 = self._get_messages_calendar(db.cursor(), username)
            if r1:
                res.extend(r1)
        res.sort()
        return res

    def _get_messages_by_type(self, cursor, username: str, type_: MessageType,
                              time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        table_name = f'Msg_{hashlib.md5(username.encode("utf-8")).hexdigest()}'
        if not self.table_exists(cursor, table_name):
            return None
        if time_range:
            start_time, end_time = convert_to_timestamp(time_range)
        local_type = get_local_type(type_)
        sql = f'''
select {MessageDB.columns}
from {table_name} as msg
join Name2Id on msg.real_sender_id = Name2Id.rowid
where local_type=? {'and create_time>' + str(start_time) + ' AND create_time<' + str(end_time) if time_range else ''}
order by sort_seq
        '''
        cursor.execute(sql, [local_type])
        result = cursor.fetchall()
        if result:
            return result
        else:
            return None

    def get_messages_by_type(self, username: str, type_: MessageType,
                             time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # 创建一个任务列表
            futures = [
                executor.submit(self._get_messages_by_type, db.cursor(), username, type_, time_range)
                for db in self.DB
            ]

            # 等待所有任务完成，并获取结果
            results = []
            for future in concurrent.futures.as_completed(futures):
                r1 = future.result()
                if r1:
                    # results.append(future.result())
                    results.extend(r1)

        return results

    def merge(self, db_file_name):
        def task_(db_path, cursor, db):
            """
            每个线程执行的任务，获取某个数据库实例中的查询结果。
            """
            increase_data(db_path, cursor, db, 'Name2Id', 'user_name')
            increase_update_data(db_path, cursor, db, 'TimeStamp', 'timestamp')
            tgt_conn = sqlite3.connect(db_path)
            tgt_cur = tgt_conn.cursor()
            tgt_cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            result = tgt_cur.fetchall()
            tgt_cur.close()
            tgt_conn.close()

            # print(result)
            if result:
                for row in result:
                    table_name = row[0]
                    if table_name.startswith('Msg'):
                        increase_data(db_path, cursor, db, table_name, 'server_id', exclude_column='local_id')

        tasks = []
        for i in range(100):
            db_path = db_file_name.replace('0', f'{i}')
            if os.path.exists(db_path):
                # print('初始化数据库：', db_path)
                file_name = os.path.basename(db_path)
                if file_name in self.db_file_name:
                    index = self.db_file_name.index(file_name)
                    db = self.DB[index]
                    cursor = db.cursor()
                    task_(db_path, cursor, db)
                    tasks.append([db_path, cursor, db])
                else:
                    shutil.copy(db_path, os.path.join(self.db_dir, 'message', file_name))
        # print(tasks)
        # 使用线程池 (没有加快合并速度)
        # with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        #     executor.map(lambda args: task_(*args), tasks)
        self.commit()
        print(len(tasks))


if __name__ == '__main__':
    pass
