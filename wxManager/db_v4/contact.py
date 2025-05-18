#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/5 22:47 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-contact.py 
@Description : 
"""
import os
import traceback

from wxManager.merge import increase_update_data, increase_data
from wxManager.model.db_model import DataBaseBase


class ContactDB(DataBaseBase):
    def create_index(self):
        sql = "CREATE INDEX IF NOT EXISTS contact_username ON contact(username);"
        try:
            cursor = self.DB.cursor()
            cursor.execute(sql)
            self.commit()
            cursor.close()
            return True
        except:
            return False

    def get_label_by_id(self, label_id) -> str:
        sql = '''
            select label_name_ from contact_label
            where label_id_ = ?
        '''
        try:
            cursor = self.DB.cursor()
            cursor.execute(sql, [label_id])
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                return ''
        except:
            return ''

    def get_labels(self, label_id_list) -> str:
        if not label_id_list:
            return ''
        return ','.join(map(self.get_label_by_id, label_id_list.strip(',').split(',')))

    def get_contacts(self):
        if not self.open_flag:
            return []
        self.create_index()
        '''
        @return:
        a[0]:username
        a[1]:alias
        a[2]:local_type
        a[3]:flag
        a[4]:remark
        a[5]:nick_name
        a[6]:pin_yin_initial
        a[7]:remark_pin_yin_initial
        a[8]:small_head_url
        a[9]:big_head_url
        a[10]:extra_buffer
        a[11]:head_img_md5
        a[12]:
        a[13]:
        a[14]:
        '''
        sql = '''
SELECT username, alias, local_type, flag, remark, nick_name, pin_yin_initial, remark_pin_yin_initial, small_head_url, big_head_url,extra_buffer,head_img_md5,chat_room_notify,is_in_chat_room,description,chat_room_type
FROM contact
WHERE (local_type=1 or local_type=2 or local_type=5)
ORDER BY
    CASE
        WHEN remark_quan_pin = '' THEN quan_pin
        ELSE remark_quan_pin
    END ASC
        '''
        self.cursor.execute(sql)
        results = self.cursor.fetchall()
        self.DB.commit()
        return results

    def get_contact_by_username(self, username):
        sql = '''
SELECT username, alias, local_type,flag, remark, nick_name, pin_yin_initial, remark_pin_yin_initial, small_head_url, big_head_url,extra_buffer,head_img_md5,chat_room_notify,is_in_chat_room,description,chat_room_type
FROM contact
WHERE username=?
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql, [username])
        result = cursor.fetchone()
        cursor.close()
        # self.commit()
        if result:
            return result
        return None

    def get_chatroom_info(self, username):
        sql = '''
select id,ext_buffer,username,owner
from chat_room
where username=?
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql, [username])
        result = cursor.fetchone()
        cursor.close()
        if result:
            return result
        return None

    def set_remark(self, username, remark):
        if not remark:
            return False
        sql = '''
        update contact
        set remark=?
        where username=?
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql, [remark, username])
        cursor.close()
        self.commit()
        return True

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_update_data(db_path, self.cursor, self.DB, 'biz_info', 'username')
            increase_update_data(db_path, self.cursor, self.DB, 'chat_room', 'username')
            increase_update_data(db_path, self.cursor, self.DB, 'chat_room_info_detail', 'room_id_')
            increase_update_data(db_path, self.cursor, self.DB, 'contact', 'username')
            increase_update_data(db_path, self.cursor, self.DB, 'contact_label', 'label_id_')
            increase_update_data(db_path, self.cursor, self.DB, 'openim_acct_type', 'lang_id')
            increase_update_data(db_path, self.cursor, self.DB, 'openim_appid', 'lang_id')
            # increase_update_data(db_path, self.cursor, self.DB, 'chat_room_member', 'room_id_')
            increase_data(db_path, self.cursor, self.DB, 'name2id', 'username')
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()


if __name__ == '__main__':
    pass
