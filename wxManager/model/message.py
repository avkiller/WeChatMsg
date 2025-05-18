#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
@Time        : 2024/12/10 21:03 
@Author      : SiYuan 
@Email       : 863909694@qq.com 
@File        : MemoTrace-message.py 
@Description : 
"""
from dataclasses import dataclass
from typing import List
from datetime import datetime

import xmltodict


class MessageType:
    Unknown = -1
    Text = 1
    Text2 = 2
    Image = 3
    Audio = 34
    BusinessCard = 42
    Video = 43
    Emoji = 47
    Position = 48
    Voip = 50
    OpenIMBCard = 66
    System = 10000
    File = 25769803825
    LinkMessage = 21474836529
    LinkMessage2 = 292057776177
    Music = 12884901937
    LinkMessage4 = 4294967345
    LinkMessage5 = 326417514545
    LinkMessage6 = 17179869233
    RedEnvelope = 8594229559345
    Transfer = 8589934592049
    Quote = 244813135921
    MergedMessages = 81604378673
    Applet = 141733920817
    Applet2 = 154618822705
    WeChatVideo = 219043332145
    FavNote = 103079215153
    Pat = 266287972401

    @classmethod
    def name(cls, type_):
        type_name_map = {
            cls.Unknown: '未知类型',
            cls.Text: '文本',
            cls.Image: '图片',
            cls.Video: '视频',
            cls.Audio: '语音',
            cls.Emoji: '表情包',
            cls.Voip: '音视频通话',
            cls.File: '文件',
            cls.Position: '位置分享',
            cls.LinkMessage: '分享链接',
            cls.LinkMessage2: '分享链接',
            cls.LinkMessage4: '分享链接',
            cls.LinkMessage5: '分享链接',
            cls.LinkMessage6: '分享链接',
            cls.RedEnvelope: '红包',
            cls.Transfer: '转账',
            cls.Quote: '引用消息',
            cls.MergedMessages: '合并转发的聊天记录',
            cls.Applet: '小程序',
            cls.Applet2: '小程序',
            cls.WeChatVideo: '视频号',
            cls.Music: '音乐分享',
            cls.FavNote: '收藏笔记',
            cls.BusinessCard: '个人/公众号名片',
            cls.OpenIMBCard: '企业微信名片',
            cls.System: '系统消息',
            cls.Pat: '拍一拍'
        }
        return type_name_map.get(type_, '未知类型')


@dataclass
class Message:
    local_id: int  # 消息ID
    server_id: int  # 消息的唯一ID
    sort_seq: int  # 排序用的id
    timestamp: int  # 发送秒级时间戳
    str_time: str  # 格式化时间 2024-12-01 12:00:00
    type: MessageType  # 消息类型（文本、图片、视频等）
    talker_id: str  # 聊天对象的wxid，好友的wxid或者群聊的wxid
    is_sender: bool  # 自己是否是发送者
    sender_id: str  # 消息发送者的ID
    display_name: str  # 消息发送者的对外展示的昵称（备注名，群昵称）
    avatar_src: str  # 消息发送者头像
    status: int  # 消息状态
    xml_content: str  # xml数据

    def is_chatroom(self) -> bool:
        return self.talker_id.endswith('@chatroom')

    def to_json(self) -> dict:
        try:
            xml_dict = xmltodict.parse(self.xml_content)
        except:
            xml_dict = {}
        return {
            'type': str(self.type),
            'is_send': self.is_sender,
            'timestamp': self.timestamp,
            'server_id': str(self.server_id),
            'display_name': self.display_name,
            'avatar_src': self.avatar_src,
            'xml_dict': xml_dict
        }

    def type_name(self):
        # 获取消息类型的文字描述
        return MessageType.name(self.type)

    def to_text(self):
        try:
            return f'{self.type}\n{xmltodict.parse(self.xml_content)}'
        except:
            print(self.xml_content)
            return f'{self.type}\n{self.xml_content}'

    def __lt__(self, other):
        return self.sort_seq < other.sort_seq


@dataclass
class TextMessage(Message):
    # 文本消息
    content: str

    def to_text(self):
        return self.content

    def to_json(self) -> dict:
        data = super().to_json()
        data['text'] = self.content
        return data


@dataclass
class QuoteMessage(TextMessage):
    # 引用消息
    quote_message: Message

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                "text": self.content,
                'quote_server_id': f'{self.quote_message.server_id}',
                'quote_type': self.quote_message.type,
            }
        )
        if self.quote_message.type == MessageType.Quote:
            # 防止递归引用
            data['quote_text'] = f'{self.quote_message.display_name}: {self.quote_message.content}'
        else:
            data['quote_text'] = f'{self.quote_message.display_name}: {self.quote_message.to_text()}'
        return data

    def to_text(self):
        if self.quote_message.type == MessageType.Quote:
            # 防止递归引用
            return f'{self.content}\n引用：{self.quote_message.display_name}: {self.quote_message.content}'
        else:
            return f'{self.content}\n引用：{self.quote_message.display_name}: {self.quote_message.to_text()}'


@dataclass
class FileMessage(Message):
    # 文件消息
    path: str
    md5: str
    file_size: int
    file_name: str
    file_type: str

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'path': self.path,
                'file_name': self.file_name,
                'file_size': self.file_size,
                'file_type': self.file_type
            }
        )
        return data

    def get_file_size(self, format_='MB'):
        # 定义转换因子
        units = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
        }

        # 将文件大小转换为指定格式
        if format_ in units:
            size_in_format = self.file_size / units[format_]
            return f'{size_in_format:.2f} {format_}'
        else:
            raise ValueError(f'Unsupported format: {format_}')

    def set_file_name(self, file_name=''):
        if file_name:
            self.file_name = file_name
            return True
        # 把时间戳转换为格式化时间
        time_struct = datetime.fromtimestamp(self.timestamp)  # 首先把时间戳转换为结构化时间
        str_time = time_struct.strftime("%Y%m%d_%H%M%S")  # 把结构化时间转换为格式化时间
        str_time = f'{str_time}_{str(self.server_id)[:6]}'
        if self.is_sender:
            str_time += '_1'
        else:
            str_time += '_0'
        self.file_name = str_time
        return True

    def to_text(self):
        return f'【文件】{self.file_name} {self.get_file_size()} {self.path} {self.file_type} {self.md5}'


@dataclass
class ImageMessage(FileMessage):
    # 图片消息
    thumb_path: str

    def to_json(self) -> dict:
        data = super().to_json()
        data['path'] = self.path
        data['thumb_path'] = self.thumb_path
        return data

    def to_text(self):
        return f'【图片】'


@dataclass
class EmojiMessage(ImageMessage):
    # 表情包
    url: str
    thumb_url: str
    description: str

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'path': self.url,
                'desc': self.description
            }
        )
        return data

    def to_text(self):
        return f'【表情包】 {self.description}'


@dataclass
class VideoMessage(FileMessage):
    # 视频消息
    thumb_path: str
    duration: int
    raw_md5: str

    def to_text(self):
        return '【视频】'

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'path': self.path,
                'thumb_path': self.thumb_path,
                'duration': self.duration
            }
        )
        return data


@dataclass
class AudioMessage(FileMessage):
    # 语音消息
    duration: int
    audio_text: str

    def set_file_name(self):
        # 把时间戳转换为格式化时间
        time_struct = datetime.fromtimestamp(self.timestamp)  # 首先把时间戳转换为结构化时间
        str_time = time_struct.strftime("%Y%m%d_%H%M%S")  # 把结构化时间转换为格式化时间
        str_time = f'{str_time}_{str(self.server_id)[:6]}'
        if self.is_sender:
            str_time += '_1'
        else:
            str_time += '_0'
        self.file_name = str_time

    def get_file_name(self):
        return self.file_name

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'path': self.path,
                'voice_to_text': self.audio_text,
                'duration': self.duration,
            }
        )
        return data

    def to_text(self):
        # return f'{self.server_id}\n{self.type}\n{xmltodict.parse(self.xml_content)}'
        return f'【语音】{self.audio_text}'


@dataclass
class LinkMessage(Message):
    # 链接消息
    href: str  # 跳转链接
    title: str  # 标题
    description: str  # 描述/音乐作者
    cover_path: str  # 本地封面路径
    cover_url: str  # 封面地址
    app_name: str  # 应用名
    app_icon: str  # 应用logo
    app_id: str  # app ip

    def to_text(self):
        return f'''【分享链接】
标题：{self.title}
描述：{self.description}
链接: {self.href}
应用：{self.app_name}
'''

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'url': self.href,
                'title': self.title,
                'description': self.description,
                'cover_url': self.cover_url,
                'app_logo': self.app_icon,
                'app_name': self.app_name,
            }
        )
        return data


@dataclass
class WeChatVideoMessage(Message):
    # 视频号消息
    url: str  # 下载地址
    publisher_nickname: str  # 视频发布者昵称
    publisher_avatar: str  # 视频发布者头像
    description: str  # 视频描述
    media_count: int  # 视频个数
    cover_path: str  # 封面本地路径
    cover_url: str  # 封面网址
    thumb_url: str  # 缩略图
    duration: int  # 视频时长，单位（秒）
    width: int  # 视频宽度
    height: int  # 视频高度

    def to_text(self):
        return f'''【视频号】
描述: {self.description}
发布者: {self.publisher_nickname}
'''

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'url': self.url,
                'title': self.description,
                'cover_url': self.cover_url,
                'duration': self.duration,
                'publisher_nickname': self.publisher_nickname,
                'publisher_avatar': self.publisher_avatar
            }
        )
        return data


@dataclass
class MergedMessage(Message):
    # 合并转发的聊天记录
    title: str
    description: str
    messages: List[Message]  # 嵌套子消息
    level: int  # 嵌套层数

    def to_text(self):
        res = f'【合并转发的聊天记录】\n\n'
        for message in self.messages:
            res += f"{' ' * self.level * 4}- {message.str_time} {message.display_name}: {message.to_text()}\n"
        return res

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'title': self.title,
                'description': self.description,
                'messages': [msg.to_json() for msg in self.messages],
            }
        )
        return data


@dataclass
class VoipMessage(Message):
    # 音视频通话
    invite_type: int  # -1，1:语音通话，0:视频通话
    display_content: str  # 界面显示内容
    duration: int

    def to_text(self):
        return f'【音视频通话】\n{self.display_content}'

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'invite_type': self.invite_type,
                'display_content': self.display_content,
                'duration': self.duration
            }
        )
        return data


@dataclass
class PositionMessage(Message):
    # 位置分享
    x: float  # 经度
    y: float  # 维度
    label: str  # 详细标签
    poiname: str  # 位置点标记名
    scale: float  # 缩放率

    def to_text(self):
        return f'''【位置分享】
坐标: ({self.x},{self.y})
名称: {self.poiname}
标签: {self.label}
'''

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'x': self.x,  # 经度
                'y': self.y,  # 维度
                'label': self.label,  # 详细标签
                'poiname': self.poiname,  # 位置点标记名
                'scale': self.scale,  # 缩放率
            }
        )
        return data


@dataclass
class BusinessCardMessage(Message):
    # 名片消息
    is_open_im: bool  # 是否是企业微信
    username: str  # 名片的wxid
    nickname: str  # 名片昵称
    alias: str  # 名片微信号
    province: str  # 省份
    city: str  # 城市
    sign: str  # 签名
    sex: int  # 性别 0：未知，1：男，2：女
    small_head_url: str  # 头像
    big_head_url: str  # 头像原图
    open_im_desc: str  # 公司名
    open_im_desc_icon: str  # 公司logo

    def _sex_name(self):
        if self.sex == 0:
            return '未知'
        elif self.sex == 1:
            return '男'
        else:
            return '女'

    def to_text(self):
        if self.is_open_im:
            return f'''【名片】
公司: {self.open_im_desc}
昵称: {self.nickname}
性别: {self._sex_name()}
'''
        else:
            return f'''【名片】
微信号:{self.alias}
昵称: {self.nickname}
签名: {self.sign}
性别: {self._sex_name()}
地区: {self.province} {self.city}
'''

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'is_open_im': self.is_open_im,
                'big_head_url': self.big_head_url,  # 头像原图
                'small_head_url': self.small_head_url,  # 小头像
                'username': self.username,  # wxid
                'nickname': self.nickname,  # 昵称
                'alias': self.alias,  # 微信号
                'province': self.province,  # 省份
                'city': self.city,  # 城市
                'sex': self._sex_name(),  # int ：性别 0：未知，1：男，2：女
                'open_im_desc': self.open_im_desc,  # 公司名
                'open_im_desc_icon': self.open_im_desc_icon,  # 公司名前面的图标
            }
        )
        return data


@dataclass
class TransferMessage(Message):
    # 转账
    fee_desc: str  # 金额
    pay_memo: str  # 备注
    receiver_username: str  # 收款人
    pay_subtype: int  # 状态

    def display_content(self):
        text_info_map = {
            1: "发起转账",
            3: "已收款",
            4: "已退还",
            5: "非实时转账收款",
            7: "发起非实时转账",
            8: "未知",
            9: "未知",
        }
        return text_info_map.get(self.pay_subtype, '未知')

    def to_text(self):
        return f'''【{self.display_content()}】:{self.fee_desc}
备注: {self.pay_memo}
'''

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'text': self.display_content(),  # 显示文本
                'pay_subtype': self.pay_subtype,  # 当前状态
                'pay_memo': self.pay_memo,  # 备注
                'fee_desc': self.fee_desc  # 金额
            }
        )
        return data


@dataclass
class RedEnvelopeMessage(Message):
    # 红包
    icon_url: str  # 红包logo
    title: str
    inner_type: int

    def to_text(self):
        return f'''【红包】: {self.title}'''

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'text': self.title,  # 显示文本
                'inner_type': self.inner_type,  # 当前状态
            }
        )
        return data


@dataclass
class FavNoteMessage(Message):
    # 收藏笔记
    title: str
    description: str
    record_item: str

    def to_text(self):
        return f'''【笔记】
{self.description}
{self.record_item}
'''

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'text': self.title,  # 显示文本
                'description': self.description,  # 内容
                'record_item': self.record_item
            }
        )
        return data


@dataclass
class PatMessage(Message):
    # 拍一拍
    title: str
    from_username: str
    chat_username: str
    patted_username: str
    template: str

    def to_text(self):
        return self.title

    def to_json(self) -> dict:
        data = super().to_json()
        data.update(
            {
                'type': MessageType.System,
                'text': self.title,  # 显示文本
            }
        )
        return data


if __name__ == '__main__':
    msg = TextMessage(
        local_id=1,
        server_id=101,
        timestamp=1678901234,
        type="text",
        talker_id="wxid_12345",
        is_sender=True,
        sender_id="wxid_67890",
        display_name="John Doe",
        status=3,
        content="Hello, world!"
    )
    print(msg.status)  # 输出：3
