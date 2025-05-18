import os
import re

from exporter.exporter import ExporterBase
from wxManager import MessageType, Message
from wxManager.model import QuoteMessage, LinkMessage


def parser_date(str_date):
    # 2024-01-01 12:00:00
    return str_date[0:4], str_date[0:7], str_date[0:10]


def escape_markdown(text):
    """
    转义Markdown特殊字符。
    """
    if not text:
        return ''
    # 定义需要转义的特殊字符
    special_chars = r"([\\`*_{}[\]()#+\-.!|])"
    # 使用正则表达式添加转义符
    escaped_text = re.sub(special_chars, r"\\\1", text)
    return escaped_text


class MarkdownExporter(ExporterBase):
    def title(self, message):
        str_time = message.str_time
        return f'**{str_time[11:]} {escape_markdown(message.display_name)}**:'

    def text(self, doc, message):
        str_content = message.content
        doc.write(
            f'''{self.title(message)} {escape_markdown(str_content)}\n\n'''
        )

    def image(self, doc, message):
        doc.write(
            f'''{self.title(message)} ![图片]({message.path})\n\n'''
        )

    def audio(self, doc, message):
        voice_to_text = self.database.get_audio_text(message.server_id)
        doc.write(
            f'''{self.title(message)} [语音] {voice_to_text}\n\n'''
        )

    def emoji(self, doc, message):
        doc.write(
            f'''{self.title(message)} [表情包][{message.description}]\n\n'''
        )

    def file(self, doc, message):
        doc.write(
            f'''{self.title(message)} [文件]\n\n'''
        )

    def refermsg(self, doc, message: QuoteMessage):
        doc.write(
            f'''{self.title(message)} {message.content} \n> {escape_markdown(message.quote_message.to_text())}\n\n'''
        )

    def system_msg(self, doc, message):
        str_content = message.content
        str_time = message.str_time
        str_content = str_content.replace('<![CDATA[', "").replace(
            ' <a href="weixin://revoke_edit_click">重新编辑</a>]]>', "")
        doc.write(
            f'''> {str_time} {str_content}\n\n'''
        )

    def video(self, doc, message):
        doc.write(
            f'''{self.title(message)}\n[视频]\n\n'''
        )

    def music_share(self, doc, message: LinkMessage):
        doc.write(
            f'''{self.title(message)} {message.description} [{message.description}]({message.href}) {message.app_name}\n\n'''
        )

    def share_card(self, doc, message: LinkMessage):
        doc.write(
            f'''{self.title(message)} [{escape_markdown(message.title)}]({message.href})\n\n'''
        )

    def transfer(self, doc, message):
        doc.write(
            f'''{self.title(message)} {message.to_text()}\n\n'''
        )

    def call(self, doc, message):
        doc.write(
            f'''{self.title(message)} {message.to_text()}\n\n'''
        )

    def personal_business_card(self, doc, message):
        doc.write(
            f'''{self.title(message)}{message.to_text()}\n\n'''
        )


    def position(self, doc, message):
        doc.write(
            f'''{self.title(message)} {message.to_text()}\n\n'''
        )

    def relay(self, doc, message):
        doc.write(
            f'''{self.title(message)} {message.to_text()}\n\n'''
        )

    def applets(self, doc, message):
        doc.write(
            f'''{self.title(message)}【小程序】: {message.app_name}：[{message.title}]({message.href})\n\n'''
        )

    def media(self, doc, message):
        doc.write(
            f'''{self.title(message)} {message.to_text()}\n\n'''
        )

    def announcement(self, doc, message):
        doc.write(
            f'''{self.title(message)}{message.to_text()}\n\n'''
        )

    def add_year(self, doc, year):
        doc.write(f'## {year}\n\n')

    def add_month(self, doc, month):
        doc.write(f'### {month}\n\n')

    def add_day(self, doc, day):
        doc.write(f'#### {day}\n\n')

    def export(self):
        # 实现导出为txt的逻辑
        print(f"【开始导出 Markdown {self.contact.remark}】")
        origin_path = self.origin_path
        os.makedirs(origin_path, exist_ok=True)
        filename = os.path.join(origin_path, self.contact.remark + '.md')
        messages = self.database.get_messages(self.contact.wxid, time_range=self.time_range)
        total_steps = len(messages)
        num = 1
        years = set()
        months = set()
        days = set()
        with open(filename, mode='w', newline='', encoding='utf-8') as f:
            for index, message in enumerate(messages):
                if not self._is_running:
                    break
                if index and index % 1000 == 0:
                    self.update_progress_callback(index / total_steps)
                if not self.is_selected(message):
                    continue
                type_ = message.type
                year, month, day = parser_date(message.str_time)
                if year not in years:
                    self.add_year(f, year)
                    years.add(year)
                if month not in months:
                    self.add_month(f, month)
                    months.add(month)
                if day not in days:
                    self.add_day(f, day)
                    days.add(day)

                if self.contact.is_chatroom() and self.group_members_set:
                    contact = message[13]
                    if contact.wxid not in self.group_members_set:
                        continue
                if type_ == MessageType.Text:
                    self.text(f, message)
                elif type_ == MessageType.Image:
                    self.image(f, message)
                elif type_ == MessageType.Audio:
                    self.audio(f, message)
                elif type_ == MessageType.Video:
                    self.video(f, message)
                elif type_ == MessageType.Emoji:
                    self.emoji(f, message)
                elif type_ == MessageType.System:
                    self.system_msg(f, message)
                elif type_ == MessageType.Quote:
                    self.refermsg(f, message)
                elif type_ == MessageType.File:
                    self.file(f, message)
                elif type_ == MessageType.LinkMessage:
                    self.share_card(f, message)
                elif type_ == MessageType.Transfer:
                    self.transfer(f, message)
                elif type_ == MessageType.MergedMessages:
                    self.relay(f, message)
                elif type_ == MessageType.Applet:
                    self.applets(f, message)
                elif type_ == MessageType.WeChatVideo:
                    self.media(f, message)
                # elif type_ == MessageType.:
                #     self.announcement(f, message)
                elif type_ == MessageType.Voip:
                    self.call(f, message)
                elif type_ == MessageType.BusinessCard:
                    self.personal_business_card(f, message)
                elif type_ == MessageType.Position:
                    self.position(f, message)
        self.update_progress_callback(1)
        print(f"【完成导出 Markdown {self.contact.remark}】")
        self.finish_callback(self.exporter_id)
