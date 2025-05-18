#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2025/2/17 21:34 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-open_im_media.py 
@Description : 
"""

import os.path
import shutil
import sqlite3
import traceback

from wxManager.merge import increase_data
from wxManager.log import logger
from wxManager.model import DataBaseBase


class OpenIMMediaDB(DataBaseBase):
    def get_media_buffer(self, reserved0):
        sql = '''
            select Buf
            from OpenIMMedia
            where Reserved0 = ?
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql, [reserved0])
        result = cursor.fetchone()
        self.commit()
        if result:
            return result[0]
        else:
            return None

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_data(db_path, self.cursor, self.DB, 'OpenIMMedia', 'Reserved0', 1)
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()
