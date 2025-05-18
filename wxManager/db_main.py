#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/11 1:22 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-db_main.py 
@Description : 
"""

from abc import ABC, abstractmethod

import os
from datetime import date
from typing import List, Any, Tuple

from wxManager import MessageType
from wxManager.model.contact import Contact


class DataBaseInterface(ABC):
    def __init__(self):
        self.chatroom_members_map = {}
        self.contacts_map = {}

    def init_database(self, db_dir=''):
        raise ValueError("子类必须实现该方法")

    def close(self):
        raise ValueError("子类必须实现该方法")

    def get_session(self):
        """
        获取聊天会话窗口，在聊天界面显示
        @return:
        """
        raise ValueError("子类必须实现该方法")

    def get_messages(
            self,
            username_: str,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ):
        raise ValueError("子类必须实现该方法")

    def get_messages_by_num(self, username, start_sort_seq, msg_num=20):
        """
        获取小于start_sort_seq的msg_num个消息
        @param username:
        @param start_sort_seq:
        @param msg_num:
        @return: messages, 最后一条消息的start_sort_seq
        """
        raise ValueError("子类必须实现该方法")

    def get_message_by_server_id(self, username, server_id):
        """
        获取小于start_sort_seq的msg_num个消息
        @param username:
        @param server_id:
        @return: messages, 最后一条消息的start_sort_seq
        """
        raise ValueError("子类必须实现该方法")

    def get_messages_group_by_day(
            self,
            username_: str,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,

    ) -> dict:
        raise ValueError("子类必须实现该方法")

    def get_messages_all(self, time_range=None):
        raise ValueError("子类必须实现该方法")

    def get_message_by_num(self, username_, local_id):
        raise ValueError("子类必须实现该方法")

    def get_messages_by_type(
            self,
            username_,
            type_: MessageType,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ):
        raise ValueError("子类必须实现该方法")

    def get_messages_by_keyword(self, username_, keyword, num=5, max_len=10, time_range=None, year_='all'):
        raise ValueError("子类必须实现该方法")

    def get_messages_calendar(self, username_):
        raise ValueError("子类必须实现该方法")

    def get_messages_by_days(
            self,
            username_,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ):
        raise ValueError("子类必须实现该方法")

    def get_messages_by_month(
            self,
            username_,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ):
        raise ValueError("子类必须实现该方法")

    def get_messages_by_hour(self, username_, time_range=None, year_='all'):
        raise ValueError("子类必须实现该方法")

    def get_first_time_of_message(self, username_=''):
        raise ValueError("子类必须实现该方法")

    def get_latest_time_of_message(self, username_='', time_range=None, year_='all'):
        raise ValueError("子类必须实现该方法")

    def get_messages_number(
            self,
            username_,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ) -> int:
        raise ValueError("子类必须实现该方法")

    def get_chatted_top_contacts(
            self,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
            contain_chatroom=False,
            top_n=10
    ) -> list:
        raise ValueError("子类必须实现该方法")

    def get_send_messages_number_sum(
            self,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ) -> int:
        raise ValueError("子类必须实现该方法")

    def get_send_messages_number_by_hour(
            self,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ) -> list:
        raise ValueError("子类必须实现该方法")

    def get_message_length(
            self,
            username_='',
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ) -> int:
        raise ValueError("子类必须实现该方法")

    def get_emoji_url(self, md5: str, thumb: bool) -> str | bytes:
        raise ValueError("子类必须实现该方法")

    def get_emoji_URL(self, md5: str, thumb: bool):
        raise ValueError("子类必须实现该方法")

    def get_emoji_path(self, md5: str, output_path, thumb: bool = False, ) -> str:
        """

        @param md5:
        @param output_path:
        @param thumb:
        @return:
        """
        raise ValueError("子类必须实现该方法")

    # 图片、视频、文件
    def get_file(self, md5: bytes | str) -> str:
        raise ValueError("子类必须实现该方法")

    def get_image(self, content, bytesExtra, up_dir="", md5=None, thumb=False, talker_username='') -> str:
        raise ValueError("子类必须实现该方法")

    def get_video(self, content, bytesExtra, md5=None, thumb=False):
        raise ValueError("子类必须实现该方法")

    # 图片、视频、文件结束

    # 语音
    def get_audio(self, reserved0, output_path, open_im=False, filename=''):
        raise ValueError("子类必须实现该方法")

    def get_media_buffer(self, server_id, is_open_im=False) -> bytes:
        pass

    def get_audio_path(self, reserved0, output_path, filename=''):
        raise ValueError("子类必须实现该方法")

    def get_audio_text(self, msgSvrId):
        raise ValueError("子类必须实现该方法")

    def add_audio_txt(self, msgSvrId, text):
        raise ValueError("子类必须实现该方法")

    def update_audio_to_text(self):
        raise ValueError("子类必须实现该方法")

    # 语音结束

    def get_avatar_buffer(self, username) -> bytes:
        raise ValueError("子类必须实现该方法")

    def get_contacts(self) -> List[Contact]:
        raise ValueError("子类必须实现该方法")

    def set_remark(self, username: str, remark) -> bool:
        raise ValueError("子类必须实现该方法")

    def set_avatar_buffer(self, username, avatar_path):
        raise ValueError("子类必须实现该方法")

    def get_contact_by_username(self, wxid: str) -> Contact:
        raise ValueError("子类必须实现该方法")

    def get_chatroom_members(self, chatroom_name) -> dict[Any, Contact] | Any:
        """
        获取群成员（不包括企业微信联系人）
        @param chatroom_name:
        @return:
        """
        raise ValueError("子类必须实现该方法")

    # 联系人结束
    def merge(self, db_paths):
        """
        增量将db_path中的数据合入到数据库中，若存在冲突则以db_path中的数据为准
        @param db_paths:
        @return:
        """
        raise ValueError("子类必须实现该方法")

    def get_favorite_items(self, time_range):
        raise ValueError("子类必须实现该方法")


class Context:
    def __init__(self, interface_impl):
        """
        初始化上下文，动态加载接口实现中的所有方法和属性。
        :param interface_impl: 实现接口的具体实例
        """
        if not isinstance(interface_impl, DataBaseInterface):
            raise TypeError("interface_impl 必须是 DataBaseInterface 的子类实例")

        # 动态绑定实现类的方法和属性
        for name in dir(interface_impl):
            # 仅绑定非私有且非特殊方法
            if not name.startswith("_"):
                attr = getattr(interface_impl, name)
                setattr(self, name, attr)


if __name__ == '__main__':
    pass
