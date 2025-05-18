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
import traceback
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import date
from typing import Tuple, List, Any

import xmltodict

from wxManager import MessageType
from wxManager.db_main import DataBaseInterface
from wxManager.db_v3.audio2text import Audio2TextDB
from wxManager.db_v3.hard_link_file import HardLinkFile
from wxManager.db_v3.hard_link_image import HardLinkImage
from wxManager.db_v3.hard_link_video import HardLinkVideo

from wxManager.db_v3.misc import Misc
from wxManager.db_v3.msg import Msg
from wxManager.db_v3.media_msg import MediaMsg
from wxManager.db_v3.emotion import Emotion
from wxManager.db_v3.open_im_contact import OpenIMContactDB
from wxManager.db_v3.open_im_media import OpenIMMediaDB
from wxManager.db_v3.open_im_msg import OpenIMMsgDB
from wxManager.db_v3.public_msg import PublicMsg
from wxManager.db_v3.micro_msg import MicroMsg
from wxManager.db_v3.favorite import Favorite
from wxManager.log import logger
from wxManager.model.contact import Contact, Me, ContactType, Person
from wxManager.parser.file_parser import get_image_type
from wxManager.parser.util.protocbuf.roomdata_pb2 import ChatRoomData
from wxManager.parser.wechat_v3 import FACTORY_REGISTRY, parser_sub_type, Singleton

type_name_dict = {
    (1, 0): MessageType.Text,
    (3, 0): MessageType.Image,
    (34, 0): MessageType.Audio,
    (43, 0): MessageType.Video,
    (47, 0): MessageType.Emoji,

    (37, 0): "添加好友",
    (42, 0): MessageType.BusinessCard,
    (66, 0): MessageType.OpenIMBCard,
    (48, 0): MessageType.Position,
    (49, 40): MessageType.FavNote,
    (49, 24): MessageType.FavNote,
    (49, 53): "接龙",

    (49, 0): MessageType.File,
    (49, 1): MessageType.Text2,
    (49, 3): MessageType.Music,
    (49, 76): MessageType.Music,
    (49, 5): MessageType.LinkMessage,
    (49, 6): MessageType.File,
    (49, 8): "用户上传的GIF表情",
    (49, 17): MessageType.System,  # 发起了位置共享
    (49, 19): MessageType.MergedMessages,
    (49, 33): MessageType.Applet,
    (49, 36): MessageType.Applet2,
    (49, 51): MessageType.WeChatVideo,
    (49, 57): MessageType.Quote,
    (49, 63): "视频号直播或直播回放等",
    (49, 87): "群公告",
    (49, 88): "视频号直播或直播回放等",
    (49, 2000): MessageType.Transfer,
    (49, 2003): "赠送红包封面",

    (50, 0): MessageType.Voip,
    (10000, 0): MessageType.System,
    (10000, 4): MessageType.Pat,
    (10000, 8000): MessageType.System
}


def decodeExtraBuf(extra_buf_content: bytes):
    if not extra_buf_content:
        return {
            "region": ('', '', ''),
            "signature": '',
            "telephone": '',
            "gender": 0,
        }
    trunkName = {
        b"\x46\xCF\x10\xC4": "个性签名",
        b"\xA4\xD9\x02\x4A": "国家",
        b"\xE2\xEA\xA8\xD1": "省份",
        b"\x1D\x02\x5B\xBF": "市",
        # b"\x81\xAE\x19\xB4": "朋友圈背景url",
        # b"\xF9\x17\xBC\xC0": "公司名称",
        # b"\x4E\xB9\x6D\x85": "企业微信属性",
        # b"\x0E\x71\x9F\x13": "备注图片",
        b"\x75\x93\x78\xAD": "手机号",
        b"\x74\x75\x2C\x06": "性别",
    }
    res = {"手机号": ""}
    off = 0
    try:
        for key in trunkName:
            trunk_head = trunkName[key]
            try:
                off = extra_buf_content.index(key) + 4
            except:
                pass
            char = extra_buf_content[off: off + 1]
            off += 1
            if char == b"\x04":  # 四个字节的int，小端序
                intContent = extra_buf_content[off: off + 4]
                off += 4
                intContent = int.from_bytes(intContent, "little")
                res[trunk_head] = intContent
            elif char == b"\x18":  # utf-16字符串
                lengthContent = extra_buf_content[off: off + 4]
                off += 4
                lengthContent = int.from_bytes(lengthContent, "little")
                strContent = extra_buf_content[off: off + lengthContent]
                off += lengthContent
                res[trunk_head] = strContent.decode("utf-16").rstrip("\x00")
        return {
            "region": (res["国家"], res["省份"], res["市"]),
            "signature": res["个性签名"],
            "telephone": res["手机号"],
            "gender": res["性别"],
        }
    except:
        logger.error(f'联系人解析错误:\n{traceback.format_exc()}')
        return {
            "region": ('', '', ''),
            "signature": '',
            "telephone": '',
            "gender": 0,
        }


def parser_messages(messages, username, db_dir=''):
    context = DataBaseV3()
    context.init_database(db_dir)
    if username.endswith('@chatroom'):
        contacts = context.get_chatroom_members(username)
    else:
        contacts = {
            Me().wxid: context.get_contact_by_username(Me().wxid),
            username: context.get_contact_by_username(username)
        }
    # FACTORY_REGISTRY[-1].set_contacts(contacts)
    Singleton.set_contacts(contacts)
    for message in messages:
        type_ = message[2]
        sub_type = parser_sub_type(message[7]) if username.endswith('@openim') else message[3]
        msg_type = type_name_dict.get((type_, sub_type))
        if msg_type not in FACTORY_REGISTRY:
            msg_type = -1
        yield FACTORY_REGISTRY[msg_type].create(message, username, context)


def _process_messages_batch(messages_batch, username, db_dir) -> List:
    """Helper function to process a batch of messages."""
    processed = []
    for message in parser_messages(messages_batch, username, db_dir):
        processed.append(message)
    return processed


class DataBaseV3(DataBaseInterface):
    # todo 把上面这一堆数据库功能整合到这一个class里，对外只暴漏一个接口
    def __init__(self):
        super().__init__()
        self.db_dir = None
        self.chatroom_members_map = {}
        self.contacts_map = {}

        self.misc_db = Misc('Misc.db')
        self.msg_db = Msg('Multi/MSG0.db', is_series=True)
        self.public_msg_db = PublicMsg('PublicMsg.db')
        self.micro_msg_db = MicroMsg('MicroMsg.db')
        self.hard_link_image_db = HardLinkImage('HardLinkImage.db')
        self.hard_link_file_db = HardLinkFile('HardLinkFile.db')
        self.hard_link_video_db = HardLinkVideo('HardLinkVideo.db')
        self.emotion_db = Emotion('Emotion.db')
        self.media_msg_db = MediaMsg('Multi/MediaMSG0.db', is_series=True)
        self.open_contact_db = OpenIMContactDB('OpenIMContact.db')
        self.open_media_db = OpenIMMediaDB('OpenIMMedia.db')
        self.open_msg_db = OpenIMMsgDB('OpenIMMsg.db')
        self.audio2text_db = Audio2TextDB('Audio2Text.db')

    def init_database(self, db_dir=''):
        # print('初始化数据库', db_dir)
        Me().load_from_json(os.path.join(db_dir, 'info.json'))  # 加载自己的信息
        flag = True
        self.db_dir = db_dir
        flag &= self.misc_db.init_database(db_dir)
        flag &= self.msg_db.init_database(db_dir)
        flag &= self.public_msg_db.init_database(db_dir)
        flag &= self.micro_msg_db.init_database(db_dir)
        flag &= self.hard_link_image_db.init_database(db_dir)
        flag &= self.hard_link_file_db.init_database(db_dir)
        flag &= self.hard_link_video_db.init_database(db_dir)
        flag &= self.emotion_db.init_database(db_dir)
        flag &= self.media_msg_db.init_database(db_dir)
        flag &= self.open_contact_db.init_database(db_dir)
        flag &= self.open_media_db.init_database(db_dir)
        flag &= self.open_msg_db.init_database(db_dir)
        flag &= self.audio2text_db.init_database(db_dir)
        if flag:
            self.audio2text_db.create()  # 初始化语音转文字数据库
        return flag
        # self.sns_db.init_database(db_dir)

        # self.audio_to_text.init_database(db_dir)
        # self.public_msg_db.init_database(db_dir)
        # self.favorite_db.init_database(db_dir)

    def close(self):
        self.misc_db.close()
        self.msg_db.close()
        self.public_msg_db.close()
        self.micro_msg_db.close()
        self.hard_link_image_db.close()
        self.hard_link_file_db.close()
        self.hard_link_video_db.close()
        self.emotion_db.close()
        self.media_msg_db.close()
        self.open_contact_db.close()
        self.open_media_db.close()
        self.open_msg_db.close()
        self.audio2text_db.close()

    def get_session(self):
        """
        获取聊天会话窗口，在聊天界面显示
        @return:
        """
        return self.micro_msg_db.get_session()

    def get_messages(
            self,
            username_: str,
            time_range: Tuple[int | float | str | date, int | float | str | date] = None,
    ):
        # todo 改成yield进行操作，多进程处理加快速度
        import time
        st = time.time()
        logger.error(f'开始获取聊天记录：{st}')
        # if username_.startswith('gh'):
        #     messages = self.public_msg_db.get_messages(username_, time_range)
        # elif username_.endswith('@openim'):
        #     messages = self.open_msg_db.get_messages_by_username(username_, time_range)
        # else:
        #     messages = self.msg_db.get_messages_by_username(username_, time_range)
        # result = []
        # for messages_ in messages:
        #     print(len(messages_))
        #     for message in parser_messages(messages_, username_, self.db_dir):
        #         result.append(message)
        # result.sort()
        # et = time.time()
        # logger.error(f'获取聊天记录完成：{et}')
        # logger.error(f'获取聊天记录耗时：{et - st:.2f}s/{len(result)}条消息')
        # return result

        res = []

        # for messages in self.message_db.get_messages_by_username(username_, time_range):
        #     for message in self.parser_messages(messages, username_):
        #         res.append(message)

        def split_list(lst, n):
            k, m = divmod(len(lst), n)
            return [lst[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

        # # # Step 1: Retrieve raw message batches
        if username_.startswith('gh_'):
            messages = self.public_msg_db.get_messages_by_username(username_, time_range)
        elif username_.endswith('@openim'):
            messages = self.open_msg_db.get_messages_by_username(username_, time_range)
        else:
            messages = self.msg_db.get_messages_by_username(username_, time_range)

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
        logger.error(f'获取聊天记录耗时：{et - st:.2f}s/{len(res)}条消息')
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
        if username.startswith('gh'):
            messages = self.public_msg_db.get_messages_by_num(username, start_sort_seq, msg_num)
        elif username.endswith('@openim'):
            messages = self.open_msg_db.get_messages_by_num(username, start_sort_seq, msg_num)
        else:
            messages = self.msg_db.get_messages_by_num(username, start_sort_seq, msg_num)
        result = []
        for messages_ in messages:
            for message in parser_messages(messages_, username, self.db_dir):
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
        message = self.msg_db.get_message_by_server_id(username, server_id)
        if message:
            messages_iter = parser_messages([message], username, self.db_dir)
            return next(messages_iter)
        return None

    def get_messages_all(self, time_range=None):
        return self.msg_db.get_messages_all(time_range)

    def get_messages_calendar(self, username_):
        return self.msg_db.get_messages_calendar(username_)

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
            messages = self.public_msg_db.get_messages_by_type(username_, type_, time_range)
        elif username_.endswith('@openim'):
            messages = self.open_msg_db.get_messages_by_type(username_, type_, time_range)
        else:
            messages = self.msg_db.get_messages_by_type(username_, type_, time_range)

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

    def get_emoji_url(self, md5: str, thumb: bool = False) -> str | bytes:
        return self.emotion_db.get_emoji_URL(md5, thumb)

    def get_emoji_path(self, md5: str, output_path, thumb: bool = False, ) -> str:
        """

        @param md5:
        @param output_path:
        @param thumb:
        @return:
        """
        data = self.emotion_db.get_emoji_data(md5, thumb)
        prefix = "th_" if thumb else ""
        f = '.' + get_image_type(data[:10])
        file_path = os.path.join(output_path, prefix + md5 + f)
        if not os.path.exists(file_path):
            try:
                with open(file_path, 'wb') as f:
                    f.write(data)
            except:
                pass
        return file_path

    def get_emoji_URL(self, md5: str, thumb: bool = False):
        return self.emotion_db.get_emoji_URL(md5, thumb)

    # 图片、视频、文件
    def get_file(self, md5: bytes | str) -> str:
        return self.hard_link_file_db.get_file(md5)

    def get_image(self, content, bytesExtra, up_dir="", md5=None, thumb=False, talker_username='') -> str:
        return self.hard_link_image_db.get_image(content, bytesExtra, up_dir, md5, thumb)

    def get_video(self, content, bytesExtra, md5=None, thumb=False):
        return self.hard_link_video_db.get_video(content, bytesExtra, md5, thumb)

    # 图片、视频、文件结束

    # 语音
    def get_media_buffer(self, server_id, is_open_im=False) -> bytes:
        if is_open_im:
            return self.open_media_db.get_media_buffer(server_id)
        else:
            return self.media_msg_db.get_media_buffer(server_id)

    def get_audio(self, reserved0, output_path, open_im=False, filename=''):
        if open_im:
            pass
        else:
            return self.media_msg_db.get_audio(reserved0, output_path, filename)

    def get_audio_path(self, reserved0, output_path, filename=''):
        return self.media_msg_db.get_audio_path(reserved0, output_path, filename)

    def get_audio_text(self, msgSvrId):
        return self.audio2text_db.get_audio_text(msgSvrId)

    def add_audio_txt(self, msgSvrId, text):
        return self.audio2text_db.add_text(msgSvrId, text)

    def update_audio_to_text(self):
        messages = self.get_messages_all()
        contacts = self.get_contacts()
        contacts_set = {contact.wxid for contact in contacts}
        for message in messages:
            if message[2] == 34:
                str_content = message[7]
                msgSvrId = message[9]
                voice_to_text = self.media_msg_db.get_audio_text(str_content)
                if voice_to_text:
                    self.audio_to_text.add_text(msgSvrId, voice_to_text)
            wxid = message[11]
            # if wxid not in contacts_set:
            #     contact = ContactDefault(wxid)
            #     self.micro_msg_db.add_contact(contact)
            #     contacts_set.add(wxid)

    # 语音结束

    # 联系人
    def get_avatar_buffer(self, username) -> bytes:
        return self.misc_db.get_avatar_buffer(username)

    def create_contact(self, contact_info_list) -> Person:
        detail = decodeExtraBuf(contact_info_list[9])
        wxid = contact_info_list[0]
        nickname = contact_info_list[4]
        remark = contact_info_list[3]
        if not nickname and wxid.endswith('@chatroom'):
            nickname = self._get_chatroom_name(contact_info_list[0])
        if not remark:
            remark = nickname
        gender = '未知'
        signature = ''
        label_list = contact_info_list[10].split(',') if contact_info_list[10] else []
        region = ('', '', '')
        if detail:
            gender_code = detail.get('gender', 0)
            if gender_code == 1:
                gender = '男'
            elif gender_code == 2:
                gender = '女'
        type_ = contact_info_list[2]
        wxid = contact_info_list[0]
        contact = Contact(
            wxid=contact_info_list[0],
            remark=remark,
            alias=contact_info_list[1],
            nickname=nickname,
            small_head_img_url=contact_info_list[7],
            big_head_img_url=contact_info_list[8],
            flag=contact_info_list[3],
            gender=gender,
            signature=signature,
            label_list=label_list,
            region=region
        )
        contact.type = ContactType.Normal
        if wxid.startswith('gh_'):
            contact.type |= ContactType.Public
        elif wxid.endswith('@chatroom'):
            contact.type |= ContactType.Chatroom

        def is_nth_bit_set(number, n):
            # 左移 1 到第 n 位
            mask = 1 << n
            # 使用位与运算判断第 n 位
            return (number & mask) != 0

        if is_nth_bit_set(type_, 6):
            contact.type |= ContactType.Star
        if is_nth_bit_set(type_, 11):
            contact.type |= ContactType.Sticky
        if type_ == 10086:
            contact.type = ContactType.Unknown
            contact.is_unknown = True
        contact.remark = re.sub(r'[\\/:*?"<>|\s\.\x00-\x08\x0B\x0C\x0E-\x1F]', '_', contact.remark)
        return contact

    def create_open_im_contact(self, contact_info_list) -> Person:
        contact_info = {
            'UserName': contact_info_list[0],
            'Alias': contact_info_list[0],
            'Type': contact_info_list[2],
            'Remark': contact_info_list[3],
            'NickName': contact_info_list[1],
            'smallHeadImgUrl': contact_info_list[5],
            'bigHeadImgUrl': contact_info_list[4],
            'detail': None,
            'label_name': '',
            'wording': contact_info_list[13]
        }
        wxid = contact_info_list[0]
        nickname = contact_info_list[1]
        remark = contact_info_list[3]
        if not nickname and wxid.endswith('@chatroom'):
            nickname = self._get_chatroom_name(contact_info_list[0])
        if not remark:
            remark = nickname
        contact = Contact(
            wxid=contact_info_list[0],
            alias=contact_info_list[0],
            remark=f'{remark}@{contact_info_list[13]}',
            nickname=nickname,
            small_head_img_url=contact_info_list[5],
            big_head_img_url=contact_info_list[4],
        )
        contact.type = ContactType.Normal
        contact.type |= ContactType.OpenIM
        contact.remark = re.sub(r'[\\/:*?"<>|\s\.\x00-\x08\x0B\x0C\x0E-\x1F]', '_', contact.remark)
        return contact

    def get_contacts(self) -> List[Person]:
        contacts = []
        contact_lists = self.micro_msg_db.get_contact()
        for contact_info_list in contact_lists:
            contact = self.create_contact(contact_info_list)
            contacts.append(contact)

        contact_lists = self.open_contact_db.get_contacts()
        for contact_info_list in contact_lists:
            contact = self.create_open_im_contact(contact_info_list)
            contacts.append(contact)
        return contacts

    def set_remark(self, username: str, remark) -> bool:
        if username in self.contacts_map:
            self.contacts_map[username].remark = remark
        if username.endswith('@openim'):
            return self.open_contact_db.set_remark(username, remark)
        else:
            return self.micro_msg_db.set_remark(username, remark)

    def set_avatar_buffer(self, username, avatar_path):
        return self.misc_db.set_avatar_buffer(username, avatar_path)

    def get_contact_by_username(self, wxid: str) -> Contact:
        if wxid.endswith('@openim'):
            contact_info_list = self.open_contact_db.get_contact_by_username(wxid)
            if contact_info_list:
                contact = self.create_open_im_contact(contact_info_list)
            else:
                contact = Contact(
                    wxid=wxid,
                    nickname=wxid,
                    remark=wxid
                )
        else:
            contact_info_list = self.micro_msg_db.get_contact_by_username(wxid)
            if contact_info_list:
                contact = self.create_contact(contact_info_list)
            else:
                contact = Contact(
                    wxid=wxid,
                    nickname=wxid,
                    remark=wxid
                )
        return contact

    def get_chatroom_members(self, chatroom_name) -> dict[Any, Contact] | Any:
        """
        获取群成员（不包括企业微信联系人）
        @param chatroom_name:
        @return:
        """
        if chatroom_name in self.chatroom_members_map:
            return self.chatroom_members_map[chatroom_name]
        result = {}
        chatroom = self.micro_msg_db.get_chatroom_info(chatroom_name)
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
        """
        获取没有命名的群聊名
        :param wxid:
        :return:
        """
        chatroom = self.micro_msg_db.get_chatroom_info(wxid)

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
        merge_tasks = {
            self.msg_db: os.path.join(db_dir, 'Multi', 'MSG0.db'),
            self.media_msg_db: os.path.join(db_dir, 'Multi', 'MediaMSG0.db'),
            self.misc_db: os.path.join(db_dir, 'Misc.db'),
            self.micro_msg_db: os.path.join(db_dir, 'MicroMsg.db'),
            self.emotion_db: os.path.join(db_dir, 'Emotion.db'),
            self.hard_link_file_db: os.path.join(db_dir, 'HardLinkFile.db'),
            self.hard_link_image_db: os.path.join(db_dir, 'HardLinkImage.db'),
            self.hard_link_video_db: os.path.join(db_dir, 'HardLinkVideo.db'),
            self.open_contact_db: os.path.join(db_dir, 'OpenIMContact.db'),
            self.open_media_db: os.path.join(db_dir, 'OpenIMMedia.db'),
            self.open_msg_db: os.path.join(db_dir, 'OpenIMMsg.db'),
            self.public_msg_db: os.path.join(db_dir, 'PublicMsg.db'),
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
