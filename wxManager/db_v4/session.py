#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/7 0:04 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-session.py 
@Description : 
"""
import os
import traceback

from wxManager.merge import increase_update_data
from wxManager.model.db_model import DataBaseBase


class SessionDB(DataBaseBase):
    def get_session(self):
        if not self.open_flag:
            return []
        sql = '''
select username, type, unread_count, unread_first_msg_srv_id,last_timestamp, summary,last_msg_type,last_msg_sub_type,strftime('%Y/%m/%d', last_timestamp, 'unixepoch','localtime') AS strTime,last_sender_display_name,last_msg_sender
from SessionTable
order by sort_timestamp desc
        '''
        self.cursor.execute(sql)
        result = self.cursor.fetchall()
        self.commit()
        if result:
            return result
        else:
            return []

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_update_data(db_path, self.cursor, self.DB, 'SessionTable', 'username')
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()
