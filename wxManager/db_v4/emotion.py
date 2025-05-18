#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/12 18:10 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-emotion.py 
@Description : 
"""
import os
import traceback

from wxManager.merge import increase_data
from wxManager.model import DataBaseBase


class EmotionDB(DataBaseBase):
    def get_emoji_url(self, md5, thumb=False):
        emoji_info = self._get_emoji_info(md5)
        if emoji_info:
            return emoji_info[1] if thumb else emoji_info[2]
        else:
            return ''

    def _get_emoji_info(self, md5):
        sql = '''
        select aes_key,thumb_url,cdn_url
        from kNonStoreEmoticonTable
        where md5=?
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql, [md5])
        result = cursor.fetchone()
        if result:
            return result
        else:
            return None

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_data(db_path, self.cursor, self.DB, 'kNonStoreEmoticonTable', 'md5')
            increase_data(db_path, self.cursor, self.DB, 'kStoreEmoticonCaptionsTable', 'md5_')
            increase_data(db_path, self.cursor, self.DB, 'kStoreEmoticonFilesTable', 'md5_')
            increase_data(db_path, self.cursor, self.DB, 'kStoreEmoticonPackageTable', 'package_id_')
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()


if __name__ == '__main__':
    pass
