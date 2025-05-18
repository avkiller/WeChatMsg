#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/5 22:47 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-db_model.py 
@Description : 
"""
import os
import sqlite3
import traceback


class DataBaseBase:
    def __init__(self, db_file_name, is_series=False):
        self.DB = None
        self.cursor = None
        self.open_flag = False
        self.db_file_name = db_file_name
        self.is_series = is_series  # 是否是一系列数据库，例如MSG0、MSG1、MSG2······
        self.db_dir = ''

    def init_database(self, db_dir=''):
        self.db_dir = db_dir
        if not os.path.exists(db_dir):
            return False
        db_path = os.path.join(db_dir, self.db_file_name)
        if not os.path.exists(db_path) and self.db_file_name != 'Audio2Text.db':
            return False
        db_file_name = self.db_file_name
        if self.is_series:
            self.db_file_name = []
            self.DB = []
            self.cursor = []
            for i in range(100):
                new_file_name = db_file_name.replace('0', f'{i}')
                db_path = os.path.join(db_dir, new_file_name)
                if os.path.exists(db_path):
                    self.db_file_name.append(os.path.basename(new_file_name))
                    # print('初始化数据库：', db_path)
                    DB = sqlite3.connect(db_path, check_same_thread=False)
                    cursor = DB.cursor()
                    self.DB.append(DB)
                    self.cursor.append(cursor)
                    self.open_flag = True
        else:
            self.DB = sqlite3.connect(db_path, check_same_thread=False)
            # '''创建游标'''
            self.cursor = self.DB.cursor()
            self.open_flag = True
        # print('初始化数据库完成：', db_path)
        self.self_init()
        return True

    def self_init(self):
        pass

    def commit(self):
        if self.is_series:
            for db in self.DB:
                db.commit()
        else:
            self.DB.commit()

    def execute(self, sql, args):
        self.cursor.execute(sql, args)

    def close(self):
        if self.open_flag:
            try:
                self.open_flag = False
                if self.is_series:
                    for db in self.DB:
                        db.close()
                else:
                    if self.DB:
                        self.DB.close()
            except:
                print(traceback.format_exc())
            finally:
                pass

    def merge(self, db_path):
        pass

    def __del__(self):
        self.close()


if __name__ == '__main__':
    pass
