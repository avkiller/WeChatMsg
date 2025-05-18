#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2025/4/1 20:31 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : wxManager-audio2text.py 
@Description : 
"""

import os
import sqlite3
import traceback

from wxManager.merge import increase_update_data, increase_data
from wxManager.model.db_model import DataBaseBase


class Audio2TextDB(DataBaseBase):
    def create(self):
        sql = '''
        CREATE TABLE IF NOT EXISTS Audio2Text (
           ID INTEGER PRIMARY KEY,
           msgSvrId INTEGER UNIQUE,
           Text TEXT NOT NULL
           );
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql)
        # 创建索引
        cursor.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_msg_id ON Audio2Text (msgSvrId);''')
        self.commit()

    def get_audio_text(self, server_id):
        sql = '''select text from Audio2Text where msgSvrId=?'''
        cursor = self.DB.cursor()
        cursor.execute(sql, [server_id])
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return ''

    def add_text(self, server_id, text):
        try:
            cursor = self.DB.cursor()
            sql = '''INSERT INTO Audio2Text (msgSvrId, Text) VALUES (?, ?)'''
            cursor.execute(sql, [server_id, text])
            self.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        except:
            return False

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_data(db_path, self.cursor, self.DB, 'Audio2Text', 'msgSvrId')
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()
