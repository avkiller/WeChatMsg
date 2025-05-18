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
import os
from abc import ABC, abstractmethod
import lz4.block
import xmltodict

from wxManager.model.message import BusinessCardMessage, VoipMessage, MergedMessage, WeChatVideoMessage, \
    PositionMessage, TransferMessage, RedEnvelopeMessage, FavNoteMessage, PatMessage
from wxManager.parser.link_parser import parser_link, parser_applet, parser_business, parser_voip, \
    parser_merged_messages, parser_wechat_video, parser_position, parser_reply, parser_transfer, parser_red_envelop, \
    parser_file, parser_favorite_note, parser_pat, parser_music
from wxManager.parser.util.protocbuf.msg_pb2 import MessageBytesExtra
from wxManager.parser.wechat_v4 import LimitedDict
from .audio_parser import parser_audio
from .emoji_parser import parser_emoji
from .file_parser import parse_video
from wxManager.log import logger
from wxManager.model import Message, TextMessage, ImageMessage, VideoMessage, EmojiMessage, LinkMessage, FileMessage, \
    AudioMessage, QuoteMessage, MessageType
from wxManager.model import Me
from ..db_main import DataBaseInterface

'''
local_id,server_id,local_type,sort_seq,sender_username,
create_time,StrTime,status,upload_status,server_seq,origin_source,
source,message_content,compress_content"
'''


def decompress(data):
    """
    解压缩Msg：CompressContent内容
    :param data:
    :return:
    """
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if not isinstance(data, bytes):
        return ""
    try:
        dst = lz4.block.decompress(data, uncompressed_size=len(data) << 10)
        decoded_string = dst.decode().replace("\x00", "")  # Remove any null characters
    except:
        print(
            "Decompression failed: potentially corrupt input or insufficient buffer size."
        )
        return ""
    return decoded_string


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

    def common_attribute(self, message, username, manager):
        """

        :param message:
        :param username:
        :param manager:
        :return: wxid,is_sender,xml_content
        """
        is_sender = message[4]
        wxid = ''
        if is_sender:
            wxid = Me().wxid
        else:
            if username.endswith('@chatroom'):
                msgbytes = MessageBytesExtra()
                msgbytes.ParseFromString(message[10])
                for tmp in msgbytes.message2:
                    if tmp.field1 != 1:
                        continue
                    wxid = tmp.field2
                # todo 解析还是有问题，会出现这种带:的东西
                if ':' in wxid:  # wxid_ewi8gfgpp0eu22:25319:1
                    wxid = wxid.split(':')[0]
            else:
                wxid = username
        if wxid not in self.contacts:
            self.contacts[wxid] = manager.get_contact_by_username(wxid)
        if username.endswith('@openim'):
            xml_content = message[7]
        else:
            xml_content = decompress(message[11])
        xml_content = xml_content.replace('&#x01;', '').replace('&#x20;', ' ') if xml_content else ''
        return is_sender, wxid, xml_content if xml_content else message[7]

    @classmethod
    def get_message_by_server_id(cls, server_id, username, manager):
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


class UnknownMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, xml_content = self.common_attribute(message, username, manager)
        return Message(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Unknown,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[6],
            xml_content=xml_content
        )


class TextMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, xml_content = self.common_attribute(message, username, manager)
        sub_type = parser_sub_type(message[7]) if username.endswith('@openim') else message[3]
        if sub_type == 1:
            content = xmltodict.parse(xml_content).get('msg', {}).get('appmsg', {}).get('title', '')
        else:
            content = message[7]
        msg = TextMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Text,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[6],
            xml_content='',
            content=content
        )
        self.add_message(msg)
        return msg


class ImageMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, xml_content = self.common_attribute(message, username, manager)
        str_content = message[7]
        BytesExtra = message[10]
        msg = ImageMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Image,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[6],
            xml_content=str_content,
            md5='',
            path='',
            thumb_path='',
            file_size=0,
            file_name='',
            file_type='png'
        )

        path = manager.get_image(content=str_content, bytesExtra=BytesExtra, up_dir='',
                                 thumb=False, talker_username=username)
        msg.path = path
        msg.thumb_path = manager.get_image(content=str_content, bytesExtra=BytesExtra, up_dir='',
                                           thumb=True, talker_username=username)
        self.add_message(msg)
        return msg


class AudioMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, xml_content = self.common_attribute(message, username, manager)
        msg = AudioMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Audio,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[6],
            xml_content=xml_content,
            md5='',
            path='',
            file_size=0,
            file_name='',
            file_type='mp3',
            audio_text='',
            duration=0
        )
        msg.set_file_name()
        audio_dic = parser_audio(msg.xml_content)
        msg.duration = audio_dic.get('audio_length', 0)
        msg.audio_text = audio_dic.get('audio_text', '')
        if not msg.audio_text:
            msg.audio_text = manager.get_audio_text(msg.server_id)
        self.add_message(msg)
        return msg


class VideoMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, xml_content = self.common_attribute(message, username, manager)
        msg = VideoMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Video,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[6],
            xml_content=xml_content,
            md5='',
            path='',
            file_size=0,
            file_name='',
            file_type='mp4',
            thumb_path='',
            duration=0,
            raw_md5=''
        )
        str_content = message[7]
        BytesExtra = message[10]
        video_dic = parse_video(xml_content)
        msg.duration = video_dic.get('length', 0)
        msg.file_size = video_dic.get('size', 0)
        msg.md5 = video_dic.get('md5', '')
        msg.raw_md5 = video_dic.get('rawmd5', '')
        msg.path = manager.get_video(str_content, BytesExtra, md5=msg.md5, thumb=False)
        msg.thumb_path = manager.get_video(str_content, BytesExtra, md5=msg.md5, thumb=True)
        if not msg.path:
            msg.path = manager.get_video(str_content, BytesExtra, thumb=False)
            msg.thumb_path = manager.get_video(str_content, BytesExtra, thumb=True)
        # logger.error(f'{msg.path} {msg.thumb_path}')
        self.add_message(msg)
        return msg


class EmojiMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, xml_content = self.common_attribute(message, username, manager)
        msg = EmojiMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Emoji,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[6],
            xml_content=message[7],
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
        emoji_info = parser_emoji(xml_content)
        if not emoji_info.get('url'):
            msg.url = manager.get_emoji_url(emoji_info.get('md5'))
        else:
            msg.url = emoji_info.get('url')
        msg.md5 = emoji_info.get('md5', '')
        msg.description = emoji_info.get('desc')
        self.add_message(msg)
        return msg


def parser_sub_type(xml_content):
    """
    解析sub_type（用于企业微信特殊消息）
    @param xml_content:
    @return:
    """
    sub_type = 0
    try:
        data = xmltodict.parse(xml_content)
        if data and data.get('msg'):
            data = data['msg']['appmsg']
            sub_type = int(data['type'])
    except:
        sub_type = 0
    return sub_type


# 工厂注册表
class LinkMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        msg = LinkMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.LinkMessage,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
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
        type_ = message[2]
        sub_type = parser_sub_type(message[7]) if username.endswith('@openim') else message[3]
        if (type_, sub_type) in {(49, 5)}:
            info = parser_link(message_content)
            msg.title = info.get('title', '')
            msg.href = info.get('url', '')
            msg.app_name = info.get('appname', '')
            msg.app_id = info.get('appid', '')
            msg.description = info.get('desc', '')
            msg.cover_url = info.get('cover_url')
            if not msg.app_name:
                msg.app_name = info.get('sourcedisplayname')
            if not msg.app_name:
                source_username = info.get('sourceusername')
                if source_username:
                    contact = manager.get_contact_by_username(source_username)
                    msg.app_name = contact.nickname
                    msg.app_icon = contact.small_head_img_url
                    msg.app_id = source_username
        elif (type_, sub_type) in {(49, 33), (49, 36)}:
            # 小程序
            msg.type = MessageType.Applet
            info = parser_applet(message_content)
            msg.title = info.get('title', '')
            msg.href = info.get('url', '')
            msg.app_name = info.get('appname', '')
            msg.app_id = info.get('appid', '')
            msg.description = info.get('desc', '')
            msg.app_icon = info.get('app_icon', '')
            msg.cover_url = info.get('cover_url', '')
        elif (type_, sub_type) in {(49, 3), (49, 76)}:
            # 音乐分享
            info = parser_music(message_content)
            msg.type = MessageType.Music
            msg.title = info.get('title', '')
            msg.href = info.get('url', '')
            msg.app_name = info.get('appname', '')
            # msg.app_id = info.get('appid', '')
            msg.description = info.get('artist', '')
            # msg.app_icon = info.get('songalbumurl', '')
            msg.cover_url = info.get('songalbumurl', '')
            # logger.error(xmltodict.parse(message_content))
        self.add_message(msg)
        return msg


class BusinessCardMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_business(message_content)
        msg = BusinessCardMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.BusinessCard,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
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
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Voip,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
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
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_merged_messages(message_content, '', username, message[5])
        msg = MergedMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.MergedMessages,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            title=info.get('title', ''),
            description=info.get('desc', ''),
            messages=info.get('messages', []),
            level=0
        )
        dir0 = ''
        month = msg.str_time[:7]  # 2025-03

        def parser_merged(merged_messages, level):
            for index, inner_msg in enumerate(merged_messages):
                if inner_msg.type == MessageType.Image:
                    if dir0:
                        img_suffix = f'FileStorage/MsgAttach/{hashlib.md5(username.encode("utf-8")).hexdigest()}/Thumb/{month}/{inner_msg.md5}_2.dat'
                        origin_img_path = os.path.join(Me().wx_dir,
                                                       img_suffix)
                    else:
                        path = manager.get_image(content='', md5=inner_msg.md5, bytesExtra=b'', up_dir='',
                                                 thumb=False, talker_username=username)
                        inner_msg.path = path
                        inner_msg.thumb_path = manager.get_image(content='', md5=inner_msg.md5, bytesExtra=b'',
                                                                 up_dir='',
                                                                 thumb=True, talker_username=username)
                    if not os.path.exists(os.path.join(Me().wx_dir, inner_msg.path)) or inner_msg.path == '.':
                        inner_msg.path = f'FileStorage/MsgAttach/{hashlib.md5(username.encode("utf-8")).hexdigest()}/Thumb/{month}/{inner_msg.md5}_{2}.dat'
                    print(inner_msg.path)
                elif inner_msg.type == MessageType.Video:
                    if dir0:
                        inner_msg.path = os.path.join('msg', 'attach',
                                                      hashlib.md5(username.encode("utf-8")).hexdigest(),
                                                      month,
                                                      'Rec', dir0, 'V', f"{level}{'_' if level else ''}{index}.mp4")
                    else:
                        inner_msg.path = manager.get_video('', '', md5=inner_msg.md5, thumb=False)
                        inner_msg.thumb_path = manager.get_video('', '', md5=inner_msg.md5, thumb=True)
                elif inner_msg.type == MessageType.File:
                    if dir0:
                        inner_msg.path = os.path.join('msg', 'attach',
                                                      hashlib.md5(username.encode("utf-8")).hexdigest(),
                                                      month,
                                                      'Rec', dir0, 'F', f"{level}{'_' if level else ''}{index}",
                                                      inner_msg.file_name)
                    else:
                        inner_msg.path = manager.get_file(inner_msg.md5)
                elif inner_msg.type == MessageType.MergedMessages:
                    parser_merged(inner_msg.messages, f'{index}')

        parser_merged(msg.messages, '')
        self.add_message(msg)
        return msg


class WeChatVideoMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        msg = WeChatVideoMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.WeChatVideo,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
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
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Position,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
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
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Quote,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
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
        wxid = ''
        sub_type = parser_sub_type(message[7]) if username.endswith('@openim') else message[3]
        if sub_type == 17:
            xml_content = decompress(message[11])
            content = xmltodict.parse(xml_content).get('msg', {}).get('appmsg', {}).get('title', '')
        else:
            content = message[7]
        msg = TextMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.System,
            talker_id=username,
            is_sender=message[4],
            sender_id=wxid,
            display_name='',
            avatar_src='',
            status=message[7],
            xml_content=message[7],
            content=content,
        )
        self.add_message(msg)
        return msg


class TransferMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_transfer(message_content)
        msg = TransferMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Transfer,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
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
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.RedEnvelope,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
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
        file_path = manager.get_file(md5)
        msg = FileMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.File,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            path=file_path,
            md5=md5,
            file_type=info.get('file_type', ''),
            file_name=info.get('file_name', ''),
            file_size=info.get('file_size', 0)
        )
        self.add_message(msg)
        return msg


class FavNoteMessageFactory(MessageFactory, Singleton):
    def create(self, message, username, manager):
        is_sender, wxid, message_content = self.common_attribute(message, username, manager)
        info = parser_favorite_note(message_content)

        msg = FavNoteMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.FavNote,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
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
        # info = parser_pat(message_content)

        msg = PatMessage(
            local_id=message[0],
            server_id=message[9],
            sort_seq=message[5],
            timestamp=message[5],
            str_time=message[8],
            type=MessageType.Pat,
            talker_id=username,
            is_sender=is_sender,
            sender_id=wxid,
            display_name=self.contacts[wxid].remark,
            avatar_src=self.contacts[wxid].small_head_img_url,
            status=message[7],
            xml_content=message_content,
            title=message_content,
            from_username='',
            patted_username='',
            chat_username=username,
            template=''
        )
        self.add_message(msg)
        return msg


# 工厂注册表
FACTORY_REGISTRY = {
    -1: UnknownMessageFactory(),
    MessageType.Text: TextMessageFactory(),
    MessageType.Text2: TextMessageFactory(),
    MessageType.Image: ImageMessageFactory(),
    MessageType.Audio: AudioMessageFactory(),
    MessageType.Video: VideoMessageFactory(),
    MessageType.Emoji: EmojiMessageFactory(),
    MessageType.File: FileMessageFactory(),
    MessageType.Position: PositionMessageFactory(),
    MessageType.System: SystemMessageFactory(),
    MessageType.LinkMessage: LinkMessageFactory(),
    MessageType.LinkMessage2: LinkMessageFactory(),
    MessageType.LinkMessage4: LinkMessageFactory(),
    MessageType.LinkMessage5: LinkMessageFactory(),
    MessageType.LinkMessage6: LinkMessageFactory(),
    MessageType.Music: LinkMessageFactory(),
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
