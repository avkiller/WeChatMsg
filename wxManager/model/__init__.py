#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/10 21:02 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-__init__.py.py 
@Description : 定义抽象的数据模型如聊天记录，联系人或基类
"""

from .message import Message, MessageType, TextMessage, ImageMessage, FileMessage, VideoMessage, AudioMessage, \
    EmojiMessage, QuoteMessage, MergedMessage, LinkMessage, PositionMessage
from .db_model import DataBaseBase
from .contact import Person, Contact, OpenIMContact, Me

if __name__ == '__main__':
    pass
