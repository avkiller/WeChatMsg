#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2025/3/11 20:46 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : wxManager-2-contact.py 
@Description : 
"""
import time

from wxManager import DatabaseConnection

db_dir = ''  # 第一步解析后的数据库路径，例如：./wxid_xxxx/db_storage
db_version = 4  # 数据库版本，4 or 3

conn = DatabaseConnection(db_dir, db_version)  # 创建数据库连接
database = conn.get_interface()  # 获取数据库接口

st = time.time()
cnt = 0
contacts = database.get_contacts()
for contact in contacts:
    print(contact)
    contact.small_head_img_blog = database.get_avatar_buffer(contact.wxid)
    cnt += 1
    if contact.is_chatroom:
        print('*' * 80)
        print(contact)
        chatroom_members = database.get_chatroom_members(contact.wxid)
        print(contact.wxid, '群成员个数：', len(chatroom_members))
        for wxid, chatroom_member in chatroom_members.items():
            chatroom_member.small_head_img_blog = database.get_avatar_buffer(wxid)
            print(chatroom_member)
            cnt += 1

et = time.time()

print(f'联系人个数：{cnt} 耗时：{et - st:.2f}s')
