#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/10 21:03 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-contact.py 
@Description : 定义各种联系人
"""
from dataclasses import dataclass
import json
import os

import os.path
import re
from enum import Enum
from typing import Dict, List, Tuple


def remove_illegal_characters(text):
    # 去除 ASCII 控制字符（除了合法的制表符、换行符和回车符）
    illegal_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F]')
    return illegal_chars.sub('', text)


class Gender:
    MAN = 1
    WOMAN = 2
    UNKNOWN = 0


class ContactType:
    Sticky = 1 << 0  # 1 置顶
    Star = 1 << 1  # 2 星标
    Chatroom = 1 << 2  # 4 群聊
    Normal = 1 << 3  # 8 普通联系人
    Stranger = 1 << 4  # 16 陌生人
    OpenIM = 1 << 5  # 32 企业微信联系人
    Public = 1 << 6  # 64 公众号
    Unknown = 1 << 8  # 已解散或者退出的群聊


@dataclass
class Person:
    wxid: str
    remark: str
    nickname: str
    alias: str = ''
    small_head_img_url: str = ''
    small_head_img_blog: bytes = b''
    big_head_img_url: str = ''
    type: int = ContactType.Normal
    flag: int = 0
    gender: str = '未知'
    signature: str = ''
    label_list: List[str] = None
    region: Tuple[str, str, str] = ('', '', '')  # 地区 (国家,省份,城市)

    def is_chatroom(self):
        return self.wxid.endswith('@chatroom')  # 是否是群聊

    def is_public(self):
        return self.wxid.startswith('gh')  # 是否是公众号

    def is_open_im(self):
        return self.wxid.endswith('@openim')  # 是否是企业微信联系人

    def label_name(self):
        if self.label_list:
            return ','.join(self.label_list)
        else:
            return ''

    def __str__(self):
        return f'''
wxid:{self.wxid}
alias:{self.alias}
nickname:{self.nickname}
gender:{self.gender}
region:{self.region}
signature:{self.signature}
'''

    def to_json(self):
        return {
            'wxid': self.wxid,
            'alias': self.alias,
            'nickname': self.nickname,
            'remark': self.remark,
            'type': self.type,
            'gender': self.gender,
        }


@dataclass
class Contact(Person):
    is_unknown: bool = False  # 是否是联系人表中没有的数据
    # def __init__(self, contact_info: Dict):
    #     super().__init__()
    #     self.wxid: str = contact_info.get('UserName')
    #     self.is_chatroom = self.wxid.__contains__('@chatroom')  # 是否是群聊
    #     self.is_open_im = self.wxid.endswith('@openim')  # 是否是企业微信联系人
    #     self.is_public = self.wxid.startswith('gh')
    #     self.is_unknown = False  # 是否是联系人表中没有的数据
    #     if self.wxid.endswith('@stranger'):
    #         self.wxid = self.wxid[-16:]
    #     self.remark = contact_info.get('Remark')
    #     # Alias,Type,Remark,NickName,PYInitial,RemarkPYInitial,ContactHeadImgUrl.smallHeadImgUrl,ContactHeadImgUrl,bigHeadImgUrl
    #     self.alias = contact_info.get('Alias')
    #     self.nickname = remove_illegal_characters(contact_info.get('NickName'))
    #     if not self.nickname:
    #         self.nickname = '未命名'
    #     self.wording = contact_info.get('wording')  # 企业联系人的企业名
    #     if not self.remark:
    #         self.remark = self.nickname
    #         if self.is_open_im:
    #             self.remark += f'@{self.wording}'
    #     self.remark = re.sub(r'[\\/:*?"<>|\s\.]', '_', self.remark)
    #     self.small_head_img_url = contact_info.get('smallHeadImgUrl')
    #     self.big_head_img_url = contact_info.get('bigHeadImgUrl')
    #     self.small_head_img_blog = b''
    #
    #     self.type = contact_info.get('Type', 0)
    #     self.flag = contact_info.get('flag', 0)
    #
    #     self.gender = contact_info.get('gender', '')
    #     self.label_name = contact_info.get('label_name', '')  # 联系人的标签分类
    #     self.region = contact_info.get('region', ('', '', ''))
    #     self.signature = contact_info.get('signature', '')


class OpenIMContact(Person):
    def __init__(self, contact_info: Dict):
        super().__init__()


def singleton(cls):
    _instance = {}

    def inner():
        if cls not in _instance:
            _instance[cls] = cls()
        return _instance[cls]

    return inner


@singleton
@dataclass
class Me:
    def __init__(self):
        self.wxid = 'wxid_00112233'
        self.wx_dir = ''
        self.name = ''
        self.mobile = ''
        self.small_head_img_url = ''
        self.nickname = self.name
        self.remark = self.nickname
        self.xor_key = 0

    def to_json(self) -> dict:
        return {
            'username': self.wxid,
            'nickname': self.name,
            'wx_dir': self.wx_dir,
            'xor_key': self.xor_key
        }

    def load_from_json(self, json_file):
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                dic = json.load(f)
                self.name = dic.get('nickname', '')
                self.wxid = dic.get('username', '')
                self.wx_dir = dic.get('wx_dir', '')
                self.xor_key = dic.get('xor_key', '')

    def save_to_json(self, json_file):
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.to_json(), f, ensure_ascii=False, indent=4)
