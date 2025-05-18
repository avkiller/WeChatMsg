#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/11 1:26 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-wechat_v4.py 
@Description : 
"""
import hashlib
import html
import os.path
from collections import OrderedDict

from abc import ABC, abstractmethod

import xmltodict
import zstandard as zstd
from google.protobuf.json_format import MessageToDict

from wxManager.model.message import VoipMessage, BusinessCardMessage, MergedMessage, WeChatVideoMessage, \
    PositionMessage, TransferMessage, RedEnvelopeMessage, FavNoteMessage, PatMessage
from wxManager.parser.link_parser import parser_link, parser_voip, parser_applet, parser_business, \
    parser_merged_messages, parser_wechat_video, parser_position, parser_reply, parser_transfer, parser_red_envelop, \
    parser_file, parser_favorite_note, parser_pat
from wxManager.parser.util.protocbuf import packed_info_data_pb2, packed_info_data_merged_pb2, packed_info_data_img_pb2, \
    packed_info_data_img2_pb2
from .audio_parser import parser_audio
from .emoji_parser import parser_emoji
from .file_parser import parse_video
from wxManager.log import logger
from wxManager.model import *
from wxManager.model import Me
from ..db_main import DataBaseInterface

'''
local_id,server_id,local_type,sort_seq,sender_username,
create_time,StrTime,status,upload_status,server_seq,origin_source,
source,message_content,compress_content"
'''


def decompress(data):
    try:
        dctx = zstd.ZstdDecompressor()  # 创建解压对象
        x = dctx.decompress(data).strip(b'\x00').strip()
        return x.decode('utf-8').strip()
    except:
        return ''


class LimitedDict:
    # 数据缓存，最多存储k条数据，超出自动删除
    def __init__(self, k):
        self.k = k
        self.messages = OrderedDict()

    def __setitem__(self, key, value):
        if key in self.messages:
            # 如果键已存在，先删除再插入
            del self.messages[key]
        elif len(self.messages) >= self.k:
            # 超过限制，删除最早插入的项
            self.messages.popitem(last=False)
        self.messages[key] = value

    def __getitem__(self, key):
        return self.messages[key]

    def __delitem__(self, key):
        del self.messages[key]

    def __contains__(self, key):
        return key in self.messages

    def __repr__(self):
        return repr(self.messages)

    def get(self, key):
        return self.messages.get(key)


# 定义抽象工厂基类
class MessageFactory(ABC):
    @abstractmethod
    def create(self, data, username: str, database_manager: DataBaseInterface):
        """
        创建一个Message实例
        @param data: 从数据库获得的元组数据
        @param username: 聊天对象的wxid
        @param database_manager: 数据库管理接口
        @return:
        """
        pass


# 单例基类
class Singleton:
    _instances = {}
    contacts = {}
    messages = LimitedDict(100)

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls, *args, **kwargs)
        return cls._instances[cls]

    @classmethod
    def set_shared_data(cls, data):
        cls._shared_data = data

    @classmethod
    def get_shared_data(cls):
        return cls._shared_data

    @classmethod
    def set_contacts(cls, contacts):
        cls.contacts.update(contacts)

    @classmethod
    def get_contact(cls, wxid, database_manager: DataBaseInterface):
        if wxid in cls.contacts:
            return cls.contacts[wxid]
        else:
            contact = database_manager.get_contact_by_username(wxid)
            cls.contacts[wxid] = contact
            return contact

    @classmethod
    def get_message_by_server_id(cls, server_id, username, manager):
        if not server_id:
            msg = TextMessage(
                local_id=0,
                server_id=0,
                sort_seq=0,
                timestamp=0,
                str_time='',
                type=MessageType.Text,
                talker_id=username,
                is_sender=False,
                sender_id=username,
                display_name=username,
                avatar_src='',
                status=0,
                xml_content='',
                content='无效的消息'
            )
            return msg
        if server_id and isinstance(server_id, str):
            server_id = int(server_id)
        if server_id in cls.messages:
            return cls.messages.get(server_id)
        else:
            msg = manager.get_message_by_server_id(username, server_id)  # todo 非常耗时
            if msg:
                cls.add_message(msg)
            else:
                msg = TextMessage(
                    local_id=0,
                    server_id=0,
                    sort_seq=0,
                    timestamp=0,
                    str_time='',
                    type=MessageType.Text,
                    talker_id=username,
                    is_sender=False,
                    sender_id=username,
                    display_name=username,
                    avatar_src='',
                    status=0,
                    xml_content='',
                    content='无效的消息'
                )
            return msg

    @classmethod
    def reset_messages(cls):
        cls.messages = {}

    @classmethod
    def add_message(cls, message: Message):
        if message:
            cls.messages[message.server_id] = message

    def common_attribute(self, message, username, manager):
        is_sender = message[4] == Me().wxid
        wxid = message[4]
        if wxid not in self.contacts:
            self.contacts[wxid] = manager.get_contact_by_username(wxid)
        if isinstance(message[12], bytes):
            message_content = decompress(message[12])
            message_content = message_content.replace('&amp#x01;', '').replace('&#x20;', ' ')
            # logger.error(message_content)
        else:
            message_content = message[12]
        if username.endswith('@chatroom') and isinstance(message_content, str) and not is_sender and message[
            2] != MessageType.Pat:
            # 群聊文字消息格式：<wxid>:<content>
            message_content = ':'.join(message_content.split(':')[1:]).strip()
        if message_content and message_content.startswith(username):
            # md 微信不知道在搞什么，弄一些乱七八糟的东西 4.0.3.22
            message_content = message_content.strip(f'{username}:').replace('<?xml version="1.0"?>', '')
        return is_sender, wxid, message_content


class UnknownMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        msg = Message(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=message[2],
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
        )
        self.add_message(msg)
        return msg


class TextMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        msg = TextMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Text,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content='',
            content=message_content
        )
        self.add_message(msg)
        return msg


class ImageMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        filename = ''
        try:
            # 2025年3月微信4.0.3正式版修改了img命名方式才有了这个东西
            packed_info_data_proto = packed_info_data_img2_pb2.PackedInfoDataImg2()
            packed_info_data_proto.ParseFromString(message[14])
            # 转换为 JSON 格式
            packed_info_data = MessageToDict(packed_info_data_proto)
            image_info = packed_info_data.get('imageInfo', {})
            width = image_info.get('width', 0)
            height = image_info.get('height', 0)
            filename = image_info.get('filename', '').strip().strip('"').strip()
        except:
            pass
        if not filename:
            try:
                # 2025年3月微信测试版修改了img命名方式才有了这个东西
                packed_info_data_proto = packed_info_data_img_pb2.PackedInfoDataImg()
                packed_info_data_proto.ParseFromString(message[14])
                # 转换为 JSON 格式
                packed_info_data = MessageToDict(packed_info_data_proto)
                filename = packed_info_data.get('filename', '').strip().strip('"').strip()
            except:
                pass
        msg = ImageMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Image,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            md5='',
            path='',
            thumb_path='',
            file_size=0,
            file_name=filename,
            file_type='png'
        )
        path = manager.get_image(content=message_content, bytesExtra=msg, up_dir='',
                                 thumb=False, talker_username=username)
        msg.path = path
        msg.thumb_path = manager.get_image(content=message_content, bytesExtra=msg, up_dir='',
                                           thumb=True, talker_username=username)
        self.add_message(msg)
        return msg


class AudioMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        audio_dic = parser_audio(message_content)
        audio_length = audio_dic.get('audio_length', 0)
        audio_text = audio_dic.get('audio_text', '')
        if not audio_text:
            packed_info_data_proto = packed_info_data_pb2.PackedInfoData()
            packed_info_data_proto.ParseFromString(message[14])
            # 转换为 JSON 格式
            packed_info_data = MessageToDict(packed_info_data_proto)
            audio_text = packed_info_data.get('info', {}).get('audioTxt', '')
        if not audio_text:
            audio_text = manager.get_audio_text(message[1])
        msg = AudioMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Audio,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            md5='',
            path='',
            file_size=0,
            file_name='',
            file_type='mp3',
            audio_text=audio_text,
            duration=audio_length
        )
        msg.set_file_name()
        self.add_message(msg)
        return msg


class VideoMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        filename = ''
        try:
            # 2025年3月微信4.0.3正式版修改了img命名方式才有了这个东西
            packed_info_data_proto = packed_info_data_img2_pb2.PackedInfoDataImg2()
            packed_info_data_proto.ParseFromString(message[14])
            # 转换为 JSON 格式
            packed_info_data = MessageToDict(packed_info_data_proto)
            image_info = packed_info_data.get('videoInfo', {})
            width = image_info.get('width', 0)
            height = image_info.get('height', 0)
            filename = image_info.get('filename', '').strip().strip('"').strip()
        except:
            pass
        msg = VideoMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Video,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            md5='',
            path='',
            file_size=0,
            file_name=filename,
            file_type='mp4',
            thumb_path='',
            duration=0,
            raw_md5=''
        )
        video_dic = parse_video(message_content)
        msg.duration = video_dic.get('length', 0)
        msg.file_size = video_dic.get('size', 0)
        msg.md5 = video_dic.get('md5', '')
        msg.raw_md5 = video_dic.get('rawmd5', '')
        month = msg.str_time[:7]  # 2025-01
        if filename:
            # 微信4.0.3正式版增加
            video_dir = os.path.join('msg', 'video', month)
            video_path = os.path.join(video_dir, f'{filename}_raw.mp4')
            if os.path.exists(os.path.join(Me().wx_dir, video_path)):
                msg.path = video_path
                msg.thumb_path = os.path.join(video_dir, f'{filename}.jpg')
            else:
                msg.path = os.path.join(video_dir, f'{filename}.mp4')
                msg.thumb_path = os.path.join(video_dir, f'{filename}.jpg')
        else:
            msg.path = manager.hardlink_db.get_video(msg.raw_md5, False)
            msg.thumb_path = manager.hardlink_db.get_video(msg.raw_md5, True)
            if not msg.path:
                msg.path = manager.hardlink_db.get_video(msg.md5, False)
                msg.thumb_path = manager.hardlink_db.get_video(msg.md5, True)
            # logger.error(f'{msg.path} {msg.thumb_path}')

        self.add_message(msg)
        return msg


class EmojiMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        msg = EmojiMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Emoji,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            md5='',
            path='',
            thumb_path='',
            file_size=0,
            file_name='',
            file_type='png',
            url='',
            thumb_url='',
            description=''
        )
        emoji_info = parser_emoji(message_content)
        # logger.error(emoji_info)
        # logger.error(message_content)
        if not emoji_info.get('url'):
            msg.url = manager.get_emoji_url(emoji_info.get('md5'))
        else:
            msg.url = emoji_info.get('url')
        msg.md5 = emoji_info.get('md5', '')
        # msg.url = get_emoji_url(message_content)
        # msg.thumb_url = ''
        msg.description = emoji_info.get('desc')
        # msg.description = get_emoji_desc(message_content)
        self.add_message(msg)
        return msg


class LinkMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        msg = LinkMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.LinkMessage,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            href='',
            title='',
            description='',
            cover_path='',
            cover_url='',
            app_name='',
            app_icon='',
            app_id=''
        )
        if message[2] in {MessageType.LinkMessage, MessageType.LinkMessage2, MessageType.Music,
                          MessageType.LinkMessage4, MessageType.LinkMessage5, MessageType.LinkMessage6}:
            info = parser_link(message_content)
            msg.title = info.get('title', '')
            msg.href = info.get('url', '')
            msg.app_name = info.get('appname', '')
            msg.app_id = info.get('appid', '')
            msg.description = info.get('desc', '')
            msg.cover_url = info.get('cover_url', '')
            if message[2] in {MessageType.Music}:
                msg.type = MessageType.Music
            if not msg.app_name:
                source_username = info.get('sourceusername')
                if source_username:
                    contact = manager.get_contact_by_username(source_username)
                    msg.app_name = contact.nickname
                    msg.app_icon = contact.small_head_img_url
                    msg.app_id = source_username

        elif message[2] == MessageType.Applet or message[2] == MessageType.Applet2:
            info = parser_applet(message_content)
            msg.type = MessageType.Applet
            msg.title = info.get('title', '')
            msg.href = info.get('url', '')
            msg.app_name = info.get('appname', '')
            msg.app_id = info.get('appid', '')
            msg.description = info.get('desc', '')
            msg.app_icon = info.get('app_icon', '')
            msg.cover_url = info.get('cover_url', '')
        self.add_message(msg)
        return msg


class BusinessCardMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_business(message_content)
        msg = BusinessCardMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.BusinessCard,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            username=info.get('username', ''),
            nickname=info.get('nickname', ''),
            alias=info.get('alias', ''),
            small_head_url=info.get('smallheadimgurl', ''),
            big_head_url=info.get('bigheadimgurl', ''),
            sex=info.get('sex', 0),
            sign=info.get('sign', ''),
            province=info.get('province', ''),
            city=info.get('city', ''),
            is_open_im=message[2] == MessageType.OpenIMBCard,
            open_im_desc=info.get('openimdescicon', ''),
            open_im_desc_icon=info.get('openimdesc', '')
        )
        self.add_message(msg)
        return msg


class VoipMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_voip(message_content)
        msg = VoipMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Voip,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            invite_type=info.get('invite_type', 0),
            display_content=info.get('display_content', ''),
            duration=info.get('duration', 0)
        )
        self.add_message(msg)
        return msg


class MergedMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        """
        合并转发的聊天记录
        - 文件路径：
          - msg/attach/9e20f478899dc29eb19741386f9343c8/2025-03/Rec/409af365664e0c0d/F/5/xxx.pdf
        - 图片路径：
          - msg/attach/9e20f478899dc29eb19741386f9343c8/2025-03/Rec/409af365664e0c0d/Img/5
        - 视频路径：
          - msg/attach/9e20f478899dc29eb19741386f9343c8/2025-03/Rec/409af365664e0c0d/V/5.mp4
        9e20f478899dc29eb19741386f9343c8是wxid的md5加密，409af365664e0c0d是packed_info_data_proto字段里的dir3
        文件夹最后的5代表的该文件是合并转发的聊天记录第5条消息，如果存在嵌套的合并转发的聊天记录，则依次递归的添加上一层的文件名后缀，例如：合并转发的聊天记录有两层
        0：文件（文件夹名为0）
        1：图片 （文件名为1）
        2：合并转发的聊天记录
            0：文件（文件夹名为2_0）
            1：图片（文件名为2_1）
            2：视频（文件名为2_2.mp4）
        :param message:
        :param username:
        :param manager:
        :return:
        """
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_merged_messages(message_content, '', username, message[5])
        msg = MergedMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.MergedMessages,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            title=info.get('title', ''),
            description=info.get('desc', ''),
            messages=info.get('messages', []),
            level=0
        )
        packed_info_data_proto = packed_info_data_merged_pb2.PackedInfoData()
        packed_info_data_proto.ParseFromString(message[14])
        # 转换为 JSON 格式
        packed_info_data = MessageToDict(packed_info_data_proto)
        dir0 = packed_info_data.get('info', {}).get('dir', '')
        month = msg.str_time[:7]  # 2025-03
        rec_dir = os.path.join(Me().wx_dir, 'msg', 'attach', hashlib.md5(username.encode("utf-8")).hexdigest(), month,
                               'Rec')
        if not dir0 and os.path.exists(rec_dir):
            for file in os.listdir(rec_dir):
                if file.startswith(f'{msg.local_id}_'):
                    dir0 = file

        def parser_merged(merged_messages, level):
            for index, inner_msg in enumerate(merged_messages):
                wxid_md5 = hashlib.md5(username.encode("utf-8")).hexdigest()
                if inner_msg.type == MessageType.Image:
                    if dir0:
                        inner_msg.path = os.path.join('msg', 'attach',
                                                      wxid_md5,
                                                      month,
                                                      'Rec', dir0, 'Img', f"{level}{'_' if level else ''}{index}")
                        inner_msg.thumb_path = os.path.join('msg', 'attach',
                                                            wxid_md5,
                                                            month,
                                                            'Rec', dir0, 'Img',
                                                            f"{level}{'_' if level else ''}{index}_t")
                    else:
                        path = manager.get_image(content='', md5=inner_msg.md5, bytesExtra=inner_msg, up_dir='',
                                                 thumb=False, talker_username=username)
                        inner_msg.path = path
                        inner_msg.thumb_path = manager.get_image(content='', md5=inner_msg.md5, bytesExtra=inner_msg,
                                                                 up_dir='',
                                                                 thumb=True, talker_username=username)
                elif inner_msg.type == MessageType.Video:
                    if dir0:
                        inner_msg.path = os.path.join('msg', 'attach',
                                                      wxid_md5,
                                                      month,
                                                      'Rec', dir0, 'V', f"{level}{'_' if level else ''}{index}.mp4")
                        inner_msg.thumb_path = os.path.join('msg', 'attach',
                                                            wxid_md5,
                                                            month,
                                                            'Rec', dir0, 'Img',
                                                            f"{level}{'_' if level else ''}{index}_t")
                    else:
                        inner_msg.path = manager.get_video('', '', md5=inner_msg.md5, thumb=False)
                        inner_msg.thumb_path = manager.get_video('', '', md5=inner_msg.md5, thumb=True)
                elif inner_msg.type == MessageType.File:
                    if dir0:
                        inner_msg.path = os.path.join('msg', 'attach',
                                                      wxid_md5,
                                                      month,
                                                      'Rec', dir0, 'F', f"{level}{'_' if level else ''}{index}",
                                                      inner_msg.file_name)
                    else:
                        inner_msg.path = manager.get_file(inner_msg.md5)
                elif inner_msg.type == MessageType.MergedMessages:
                    parser_merged(inner_msg.messages, f'{index}' if not level else f'{level}_{index}')

        parser_merged(msg.messages, '')
        self.add_message(msg)
        return msg


class WeChatVideoMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        msg = WeChatVideoMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.WeChatVideo,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            url='',
            publisher_nickname='',
            publisher_avatar='',
            description='',
            media_count=1,
            cover_url='',
            thumb_url='',
            cover_path='',
            width=0,
            height=0,
            duration=0
        )
        info = parser_wechat_video(message_content)
        msg.publisher_nickname = info.get('sourcedisplayname', '')
        msg.publisher_avatar = info.get('weappiconurl', '')
        msg.description = info.get('title', '')
        msg.cover_url = info.get('cover', '')
        self.add_message(msg)
        return msg


class PositionMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        msg = PositionMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Position,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            x=0,
            y=0,
            poiname='',
            label='',
            scale=0
        )
        info = parser_position(message_content)
        msg.x = eval(info.get('x', ''))
        msg.y = eval(info.get('y', ''))
        msg.poiname = info.get('poiname', '')
        msg.label = info.get('label', '')
        msg.scale = eval(info.get('scale', ''))
        self.add_message(msg)
        return msg


class QuoteMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_reply(message_content)
        # quote_message = manager.get_message_by_server_id(username, info.get('svrid', ''))  # todo 非常耗时
        quote_message = self.get_message_by_server_id(info.get('svrid', ''), username, manager)
        msg = QuoteMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Quote,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            content=info.get('text'),
            quote_message=quote_message,
        )
        self.add_message(msg)
        return msg


class SystemMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender = message[4] == Me().wxid
        wxid = message[4]
        if wxid not in self.contacts:
            self.contacts[wxid] = manager.get_contact_by_username(wxid)
        if isinstance(message[12], bytes):
            message_content = decompress(message[12])
            try:
                dic = xmltodict.parse(message_content)
                message_content = dic.get('sysmsg', {}).get('revokemsg', {}).get('content', '')
            except:
                pass
            # logger.error(message_content)
        else:
            message_content = message[12]

        msg = TextMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.System,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            content=message_content,
        )
        self.add_message(msg)
        return msg


class TransferMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_transfer(message_content)
        msg = TransferMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Transfer,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            pay_subtype=info.get('pay_subtype', 0),
            fee_desc=info.get('fee_desc', ''),
            receiver_username=info.get('receiver_username', ''),
            pay_memo=info.get('pay_memo')
        )
        self.add_message(msg)
        return msg


class RedEnvelopeMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_red_envelop(message_content)
        msg = RedEnvelopeMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.RedEnvelope,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            title=info.get('title', ''),
            icon_url=info.get('icon_url', ''),
            inner_type=info.get('inner_type', 0)
        )
        self.add_message(msg)
        return msg


class FileMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_file(message_content)
        md5 = info.get('md5', '')
        filename = info.get('filename', '')
        if not filename:
            try:
                # 2025年3月微信4.0.3正式版修改了img命名方式才有了这个东西
                packed_info_data_proto = packed_info_data_img2_pb2.PackedInfoDataImg2()
                packed_info_data_proto.ParseFromString(message[14])
                # 转换为 JSON 格式
                packed_info_data = MessageToDict(packed_info_data_proto)
                image_info = packed_info_data.get('fileInfo', {})
                file_info = image_info.get('fileInfo', {})
                filename = file_info.get('filename', '').strip()
            except:
                pass
        msg = FileMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.File,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            path='',
            md5=md5,
            file_type=info.get('file_type', ''),
            file_name=info.get('file_name', ''),
            file_size=info.get('file_size', 0)
        )
        # file_path = manager.get_file(md5)
        if filename:
            month = msg.str_time[:7]  # 2025-01
            # 微信4.0.3正式版增加
            video_dir = os.path.join('msg', 'file', month)
            file_path = os.path.join(video_dir, f'{filename}')
            msg.path = file_path
        else:
            msg.path = manager.get_file(md5)
        self.add_message(msg)
        return msg


class FavNoteMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_favorite_note(message_content)

        msg = FavNoteMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Pat,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            title=info.get('title', ''),
            description=info.get('desc', ''),
            record_item=info.get('recorditem', '')
        )
        self.add_message(msg)
        return msg


class PatMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_pat(message_content)

        msg = PatMessage(
            local_id=message[0],
            server_id=message[1],
            sort_seq=message[3],
            timestamp=message[5],
            str_time=message[6],
            type=MessageType.Pat,
            talker_id=username,
            is_sender=is_sender,
            sender_id=message[4],
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            title=info.get('title', ''),
            from_username=info.get('from_username', ''),
            patted_username=info.get('patted_username', ''),
            chat_username=info.get('chat_username', ''),
            template=info.get('template', '')
        )
        self.add_message(msg)
        return msg


# 工厂注册表
FACTORY_REGISTRY = {
    -1: UnknownMessageFactory(),
    MessageType.Text: TextMessageFactory(),
    MessageType.Image: ImageMessageFactory(),
    MessageType.Audio: AudioMessageFactory(),
    MessageType.Video: VideoMessageFactory(),
    MessageType.Emoji: EmojiMessageFactory(),
    MessageType.File: FileMessageFactory(),
    MessageType.Position: PositionMessageFactory(),
    MessageType.System: SystemMessageFactory(),
    MessageType.LinkMessage: LinkMessageFactory(),
    MessageType.LinkMessage2: LinkMessageFactory(),
    MessageType.Music: LinkMessageFactory(),
    MessageType.LinkMessage4: LinkMessageFactory(),
    MessageType.LinkMessage5: LinkMessageFactory(),
    MessageType.LinkMessage6: LinkMessageFactory(),
    MessageType.Applet: LinkMessageFactory(),
    MessageType.Applet2: LinkMessageFactory(),
    MessageType.Voip: VoipMessageFactory(),
    MessageType.BusinessCard: BusinessCardMessageFactory(),
    MessageType.OpenIMBCard: BusinessCardMessageFactory(),
    MessageType.MergedMessages: MergedMessageFactory(),
    MessageType.WeChatVideo: WeChatVideoMessageFactory(),
    MessageType.Quote: QuoteMessageFactory(),
    MessageType.Transfer: TransferMessageFactory(),
    MessageType.RedEnvelope: RedEnvelopeMessageFactory(),
    MessageType.FavNote: FavNoteMessageFactory(),
    MessageType.Pat: PatMessageFactory(),
}

if __name__ == '__main__':
    pass
