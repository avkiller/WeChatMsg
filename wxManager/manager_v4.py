#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/11 20:43 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-manager_v4.py
@Description : 
"""
import concurrent
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed, ThreadPoolExecutor
from datetime import date, datetime
from multiprocessing import Pool, cpu_count
from typing import Tuple, List, Any

import zstandard as zstd

from wxManager import MessageType
from wxManager.db_v4.audio2text import Audio2TextDB
from wxManager.db_v4.biz_message import BizMessageDB
from wxManager.db_v4.emotion import EmotionDB
from wxManager.db_v4.media import MediaDB
from wxManager.db_v4 import ContactDB, HeadImageDB, SessionDB, MessageDB, HardLinkDB
from wxManager.db_main import DataBaseInterface, Context
from wxManager.model.contact import Contact, ContactType, Person
from wxManager.model import Me
from wxManager.parser.util.protocbuf.roomdata_pb2 import ChatRoomData
from wxManager.parser.wechat_v4 import FACTORY_REGISTRY, Singleton
from wxManager.log import logger
from wxManager.parser.util.protocbuf import contact_pb2
from google.protobuf.json_format import MessageToDict


def decompress(data):
    dctx = zstd.ZstdDecompressor()  # 创建解压对象
    x = dctx.decompress(data)
    return x.decode('utf-8')


def parser_messages(messages, username, db_dir=''):
    context = DataBaseV4()
    context.init_database(db_dir)
    if username.endswith('@chatroom'):
        contacts = context.get_chatroom_members(username)
    else:
        contacts = {
            Me().wxid: context.get_contact_by_username(Me().wxid),
            username: context.get_contact_by_username(username)
        }
    # FACTORY_REGISTRY[-1].set_contacts(contacts) # 不知道为什么用对象修改类属性每个实例对象的contacts不一样
    Singleton.set_contacts(contacts)

    for message in messages:
        type_ = message[2]
        if type_ not in FACTORY_REGISTRY:
            type_ = -1
        yield FACTORY_REGISTRY[type_].create(message, username, context)


def _process_messages_batch(messages_batch, username, db_dir) -> List:
    """Helper function to process a batch of messages."""
    processed = []
    for message in parser_messages(messages_batch, username, db_dir):
        processed.append(message)
    return processed


class DataBaseV4(DataBaseInterface):
    def __init__(self):
        super().__init__()
        self.db_dir = ''
        self.chatroom_members_map = {}
        self.contacts_map = {}

        # V4
        self.contact_db = ContactDB('contact/contact.db')
        self.head_image_db = HeadImageDB('head_image/head_image.db')
        self.session_db = SessionDB('session/session.db')
        self.message_db = MessageDB('message/message_0.db', is_series=True)
        self.biz_message_db = BizMessageDB('message/biz_message_0.db', is_series=True)
        self.media_db = MediaDB('message/media_0.db', is_series=True)
        self.hardlink_db = HardLinkDB('hardlink/hardlink.db')
        self.emotion_db = EmotionDB('emoticon/emoticon.db')
        self.audio2text_db = Audio2TextDB('Audio2Text.db')

    def init_database(self, db_dir=''):
        Me().load_from_json(os.path.join(db_dir, 'info.json'))  # 加载自己的信息
        # print('初始化数据库', db_dir)
        self.db_dir = db_dir
        flag = True
        flag &= self.contact_db.init_database(db_dir)
        flag &= self.head_image_db.init_database(db_dir)
        flag &= self.session_db.init_database(db_dir)
        flag &= self.message_db.init_database(db_dir)
        flag &= self.biz_message_db.init_database(db_dir)
        self.media_db.init_database(db_dir)
        flag &= self.hardlink_db.init_database(db_dir)
        flag &= self.emotion_db.init_database(db_dir)
        flag &= self.audio2text_db.init_database(db_dir)
        if flag:
            self.audio2text_db.create()  # 初始化语音转文字数据库
        return flag

    def close(self):
        pass

        # self.head_image_db.close()
        # self.contact_db.close()

    def get_session(self):
        """
        获取聊天会话窗口，在聊天界面显示
        @return:
        """
        return self.session_db.get_session()

    def get_messages(
            self,
            username_: str,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ):
        # todo 改成yield进行操作，多进程处理加快速度
        import time
        st = time.time()
        logger.error(f'开始获取聊天记录：{st}')
        res = []

        # messages = self.message_db.get_messages_by_username(username_, time_range)*20
        # # for messages in self.message_db.get_messages_by_username(username_, time_range):
        # for messages_ in messages:
        #     for message in parser_messages(messages_, username_, self.db_dir):
        #         res.append(message)

        def split_list(lst, n):
            k, m = divmod(len(lst), n)
            return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

        #
        # # # Step 1: Retrieve raw message batches
        if username_.startswith('gh_'):
            messages = self.biz_message_db.get_messages_by_username(username_, time_range)
        else:
            messages = self.message_db.get_messages_by_username(username_, time_range)

        if len(messages) < 20000:
            for message in parser_messages(messages, username_, self.db_dir):
                res.append(message)
        else:
            raw_message_batches = split_list(messages, len(messages) // 10000 + 1)
            #
            # # Step 2: Use multiprocessing to process the message batches
            # res = []
            # for batch in raw_message_batches:
            #     print(len(batch))

            with ProcessPoolExecutor(max_workers=min(len(raw_message_batches), 16)) as executor:
                # Submit tasks
                future_to_batch = {
                    executor.submit(_process_messages_batch, batch, username_, self.db_dir): batch
                    for batch in raw_message_batches
                }

                # Collect results
                for future in future_to_batch.keys():
                    res.extend(future.result())

        et = time.time()
        logger.error(f'获取聊天记录完成：{et}')
        logger.error(f'获取聊天记录耗时：{et - st:.2f}s/{len(res)}条消息 {username_}')
        res.sort()
        return res

    def get_messages_by_num(self, username, start_sort_seq, msg_num=20):
        """
        获取小于start_sort_seq的msg_num个消息
        @param username:
        @param start_sort_seq:
        @param msg_num:
        @return: messages, 最后一条消息的start_sort_seq
        """
        result = []
        if username.startswith('gh_'):
            messages = self.biz_message_db.get_messages_by_num(username, start_sort_seq, msg_num)
        else:
            messages = self.message_db.get_messages_by_num(username, start_sort_seq, msg_num)
        for messages in messages:
            for message in parser_messages(messages, username, self.db_dir):
                result.append(message)
        result.sort(reverse=True)
        res = result[:msg_num]
        return res, res[-1].sort_seq if res else 0

    def get_message_by_server_id(self, username, server_id):
        """
        获取小于start_sort_seq的msg_num个消息
        @param username:
        @param server_id:
        @return: messages, 最后一条消息的start_sort_seq
        """
        message = self.message_db.get_message_by_server_id(username, server_id)
        if message:
            messages_iter = parser_messages([message], username, self.db_dir)
            return next(messages_iter)
        return None

    def get_messages_by_type(
            self,
            username_,
            type_: MessageType,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ):
        def split_list(lst, n):
            k, m = divmod(len(lst), n)
            return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

        res = []
        # # # Step 1: Retrieve raw message batches
        if username_.startswith('gh_'):
            messages = self.biz_message_db.get_messages_by_type(username_, time_range)
        else:
            messages = self.message_db.get_messages_by_type(username_, type_, time_range)

        if len(messages) < 20000:
            for message in parser_messages(messages, username_, self.db_dir):
                res.append(message)
        else:
            raw_message_batches = split_list(messages, len(messages) // 10000 + 1)
            with ProcessPoolExecutor(max_workers=min(len(raw_message_batches), 16)) as executor:
                # Submit tasks
                future_to_batch = {
                    executor.submit(_process_messages_batch, batch, username_, self.db_dir): batch
                    for batch in raw_message_batches
                }
                # Collect results
                for future in future_to_batch.keys():
                    res.extend(future.result())
        res.sort()
        return res

    def get_messages_calendar(self, username_: str):
        if username_.startswith('gh_'):
            return self.biz_message_db.get_messages_calendar(username_)
        else:
            return self.message_db.get_messages_calendar(username_)

    def get_chatted_top_contacts(
            self,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
            contain_chatroom=False,
            top_n=10
    ) -> list:
        return []

    def get_emoji_url(self, md5: str, thumb: bool = False) -> str | bytes:
        return self.emotion_db.get_emoji_url(md5, thumb)

    # 图片、视频、文件
    def get_file(self, md5: bytes | str) -> str:
        return self.hardlink_db.get_file(md5)

    def get_image(self, content, bytesExtra, up_dir="", md5=None, thumb=False, talker_username='') -> str:
        return self.hardlink_db.get_image(content, bytesExtra, up_dir, md5, thumb, talker_username)

    def get_video(self, content, bytesExtra, md5=None, thumb=False):
        return self.hardlink_db.get_video(md5, thumb)

    # 语音
    def get_audio(self, reserved0, output_path, open_im=False, filename=''):
        return self.media_db.get_audio(reserved0, output_path, filename)

    def get_media_buffer(self, server_id, is_open_im=False) -> bytes:
        return self.media_db.get_media_buffer(server_id)

    def get_audio_path(self, reserved0, output_path, filename=''):
        return self.media_db.get_audio_path(reserved0, output_path, filename)

    def get_audio_text(self, server_id):
        return self.audio2text_db.get_audio_text(server_id)

    def update_audio_to_text(self):
        # todo
        return

    def add_audio_txt(self, server_id, text):
        return self.audio2text_db.add_text(server_id, text)

    # 语音结束

    # 联系人

    def get_avatar_buffer(self, username) -> bytes:
        return self.head_image_db.get_avatar_buffer(username)

    def create_contact(self, contact_info_list) -> Person:
        wxid, local_type, flag = contact_info_list[0], contact_info_list[2], contact_info_list[3]
        nickname = contact_info_list[5]
        remark = contact_info_list[4]
        if not nickname and wxid.endswith('@chatroom'):
            nickname = self._get_chatroom_name(contact_info_list[0])
        if not remark:
            remark = nickname
        gender = '未知'
        signature = ''
        label_list = []
        region = ('', '', '')
        if not (wxid.endswith('@openim') or wxid.endswith('@chatroom')):
            try:
                # 创建顶级消息对象
                message = contact_pb2.ContactInfo()
                # 解析二进制数据
                message.ParseFromString(contact_info_list[10])
                # 转换为 JSON 格式
                detail = MessageToDict(message)
                gender_code = detail.get('gender', 0)
                if gender_code == 1:
                    gender = '男'
                elif gender_code == 2:
                    gender = '女'
                label_list = detail.get('labelList', '').strip(',').split(',')
                signature = detail.get('signature', '')
                region = (detail.get('country', ''), detail.get('province', ''), detail.get('city', ''))
                label_list = self.contact_db.get_labels(detail.get('labelList')).split(',')
            except:
                pass
                # logger.error(f'{wxid} {contact_info_list[5]}联系人解析失败\n{contact_info_list[10]}')
        contact = Contact(
            wxid=contact_info_list[0],
            remark=remark,
            alias=contact_info_list[1],
            nickname=nickname,
            small_head_img_url=contact_info_list[8],
            big_head_img_url=contact_info_list[9],
            flag=contact_info_list[3],
            gender=gender,
            signature=signature,
            label_list=label_list,
            region=region
        )

        def is_nth_bit_set(number, n):
            # 左移 1 到第 n 位
            mask = 1 << n
            # 使用位与运算判断第 n 位
            return (number & mask) != 0

        if local_type == 1:
            contact.type = ContactType.Normal
            if wxid.startswith('gh_'):
                contact.type |= ContactType.Public
            elif wxid.endswith('@chatroom'):
                contact.type |= ContactType.Chatroom
        elif local_type == 2:
            contact.type = ContactType.Chatroom
        elif local_type == 3:
            contact.type = ContactType.Stranger
        elif local_type == 5:
            contact.type = ContactType.OpenIM
        if is_nth_bit_set(flag, 6):
            contact.type |= ContactType.Star
        if is_nth_bit_set(flag, 11):
            contact.type |= ContactType.Sticky
        if local_type == 10086:
            contact.type = ContactType.Unknown
            contact.is_unknown = True
        contact.remark = re.sub(r'[\\/:*?"<>|\s\.\x00-\x08\x0B\x0C\x0E-\x1F]', '_', contact.remark)
        return contact

    def get_contacts(self) -> List[Person]:
        contacts = []
        contact_lists = self.contact_db.get_contacts()
        for contact_info_list in contact_lists:
            if contact_info_list:
                contact = self.create_contact(contact_info_list)
                contacts.append(contact)
        return contacts

    def set_remark(self, username: str, remark) -> bool:
        if username in self.contacts_map:
            self.contacts_map[username].remark = remark
        return self.contact_db.set_remark(username, remark)

    def set_avatar_buffer(self, username, avatar_path):
        return self.head_image_db.set_avatar_buffer(username, avatar_path)

    def get_contact_by_username(self, wxid: str) -> Person:
        contact_info_list = self.contact_db.get_contact_by_username(wxid)
        if contact_info_list:
            contact = self.create_contact(contact_info_list)
            return contact
        else:
            contact = Contact(
                wxid=wxid,
                nickname=wxid,
                remark=wxid
            )
        return contact

    def get_chatroom_members(self, chatroom_name) -> dict[Any, Person] | Any:
        """
        获取群成员
        @param chatroom_name:
        @return:
        """
        if chatroom_name in self.chatroom_members_map:
            return self.chatroom_members_map[chatroom_name]
        result = {}
        chatroom = self.contact_db.get_chatroom_info(chatroom_name)

        if chatroom is None:
            return result
        # 解析RoomData数据
        parsechatroom = ChatRoomData()
        parsechatroom.ParseFromString(chatroom[1])
        # 群成员数据放入字典存储
        for mem in parsechatroom.members:
            contact = self.get_contact_by_username(mem.wxID)
            if contact:
                if mem.displayName:
                    contact.remark = mem.displayName
                result[contact.wxid] = contact
        self.chatroom_members_map[chatroom_name] = result
        return result

    def _get_chatroom_name(self, wxid):
        chatroom = self.contact_db.get_chatroom_info(wxid)

        if chatroom is None:
            return ''
        # 解析RoomData数据
        parsechatroom = ChatRoomData()
        parsechatroom.ParseFromString(chatroom[1])
        chatroom_name = ''
        # 群成员数据放入字典存储
        for mem in parsechatroom.members[:5]:
            if mem.wxID == Me().wxid:
                continue
            if mem.displayName:
                chatroom_name += f'{mem.displayName}、'
            else:
                contact = self.get_contact_by_username(mem.wxID)
                chatroom_name += f'{contact.remark}、'
        return chatroom_name.rstrip('、')

    # 联系人结束

    def get_favorite_items(self, time_range):
        return self.favorite_db.get_items(time_range)

    def merge(self, db_dir):
        """
        批量将db_path中的数据合入到数据库中
        @param db_path:
        @return:
        """
        merge_tasks = {
            self.head_image_db: os.path.join(db_dir, 'head_image', 'head_image.db'),
            self.hardlink_db: os.path.join(db_dir, 'hardlink', 'hardlink.db'),
            self.media_db: os.path.join(db_dir, 'message', 'media_0.db'),
            self.contact_db: os.path.join(db_dir, 'contact', 'contact.db'),
            self.emotion_db: os.path.join(db_dir, 'emoticon', 'emoticon.db'),
            self.message_db: os.path.join(db_dir, 'message', 'message_0.db'),
            self.biz_message_db: os.path.join(db_dir, 'message', 'biz_message_0.db'),
            self.session_db: os.path.join(db_dir, 'session', 'session.db'),
        }

        def merge_task(db_instance, db_path):
            """执行单个数据库的合并任务"""
            db_instance.merge(db_path)

        # 使用 ThreadPoolExecutor 进行多线程合并
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(merge_task, db, path): (db, path) for db, path in merge_tasks.items()}

            # 等待所有任务完成
            for future in concurrent.futures.as_completed(futures):
                db, path = futures[future]
                try:
                    future.result()  # 这里会抛出异常（如果有的话）
                    print(f"成功合并数据库: {path}")
                except Exception as e:
                    print(f"合并 {path} 失败: {e}")
