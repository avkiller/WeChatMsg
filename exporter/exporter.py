import csv
import html
import io
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

import pysilk

from wxManager import MessageType, DataBaseInterface
from wxManager.model import Contact, Me, Message

from wxManager.log import logger
from exporter.config import FileType


def makedirs(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(path, 'image'), exist_ok=True)
    os.makedirs(os.path.join(path, 'emoji'), exist_ok=True)
    os.makedirs(os.path.join(path, 'video'), exist_ok=True)
    os.makedirs(os.path.join(path, 'voice'), exist_ok=True)
    os.makedirs(os.path.join(path, 'file'), exist_ok=True)
    os.makedirs(os.path.join(path, 'avatar'), exist_ok=True)
    os.makedirs(os.path.join(path, 'music'), exist_ok=True)
    os.makedirs(os.path.join(path, 'icon'), exist_ok=True)


def escape_js_and_html(input_str):
    if not input_str:
        return ''
    # 转义HTML特殊字符
    html_escaped = html.escape(input_str, quote=False)

    # 手动处理JavaScript转义字符
    js_escaped = (
        html_escaped
        .replace('\\r\\n', '<br>')
        .replace('\\n', '<br>')
        .replace('\\t', '&emsp;')
        .replace("\\", "\\\\")
        .replace("'", r"\'")
        .replace('"', r'\"')
        .replace("\n", r'\n')
        .replace("\r", r'\r')
        .replace("\t", r'\t')
    )

    return js_escaped


class ExporterBaseBase:
    exporter_id = 0

    def __init__(self):
        ExporterBaseBase.exporter_id += 1
        self.id = ExporterBaseBase.exporter_id
        self._is_running = True
        self._is_paused = False

    def cancel(self):
        print('cancel')

    def pause(self):
        self._is_paused = True

    def resume(self):
        self._is_paused = False

    def stop(self):
        self._is_running = False
        self.resume()  # 确保在停止时唤醒线程


class ExporterBase(ExporterBaseBase):
    i = 1

    def __init__(
            self,
            database: DataBaseInterface,
            contact: Contact,
            output_dir,
            type_=FileType.TXT,  # 导出文件类型
            message_types: set[MessageType] = None,  # 导出的消息类型
            time_range=None,  # 导出的日期范围
            group_members: set[str] = None,  # 群聊中只导出这些人的聊天记录
            progress_callback=None,  # 进度回调函数，func(progress:float)
            finish_callback=None  # 导出完成回调函数
    ):
        """
        @param database:
        @param contact: 要导出的联系人
        @param output_dir: 输出文件夹
        @param type_: 导出文件类型
        @param message_types: 导出的消息类型
        @param time_range: 导出的日期范围
        @param group_members: 群聊中筛选的群成员
        @param progress_callback: 导出进度回调函数
        """
        super().__init__()
        if progress_callback:
            self.update_progress_callback = progress_callback
        else:
            self.update_progress_callback = self.print_progress
        if finish_callback:
            self.finish_callback = finish_callback
        else:
            self.finish_callback = self.finish
        self.database = database
        self.avatar_urls_dict = {}  # 联系人头像地址的字典
        self.avatar_urls = []  # 联系人的头像地址（写入HTML）
        self.avatar_paths_dict = {}  # 联系人本地头像地址的字典
        self.avatar_paths = []  # 联系人的本地头像地址（写入HTML）
        self.message_types = message_types  # 导出的消息类型
        self.contact: Contact = contact  # 联系人
        self.output_type = type_  # 导出文件类型
        self.total_num = 1  # 总的消息数量
        self.num = 0  # 当前处理的消息数量
        self.last_timestamp = 0
        self.time_range = time_range
        self.group_contacts = {}  # 群聊里的所有联系人
        self.group_members = group_members  # 要导出的群聊成员（用于群消息筛选）
        self.group_members_set = group_members
        self.origin_path = os.path.join(output_dir, '聊天记录', f'{self.contact.remark}({self.contact.wxid})')
        makedirs(self.origin_path)

    def print_progress(self, progress):
        logger.info(f'导出进度：{progress * 100:.2f}%')
        # print()

    def finish(self, success):
        if success:
            logger.info(f'导出完成\n{"-" * 20}')
        else:
            logger.info(f'导出失败\n{"-" * 20}')

    def set_update_callback(self, callback):
        self.update_progress_callback = callback

    def _is_select_by_type(self, message):
        # 筛选特定的消息类型
        if not self.message_types:
            return True
        else:
            return message.type in self.message_types

    def _is_select_by_contact(self, message):
        # 筛选群聊里的指定群成员
        if self.contact.is_chatroom() and self.group_members_set:
            wxid = message.sender_id
            if wxid in self.group_members_set:
                return True
            else:
                return False
        else:
            return True

    def is_selected(self, message):
        # 判断该消息是否应该导出
        return self._is_select_by_type(message) and self._is_select_by_contact(message)

    def run(self):
        self.export()

    def export(self):
        return True

    def start(self):
        self.run()

    def is_5_min(self, timestamp) -> bool:
        if abs(timestamp - self.last_timestamp) > 300:
            self.last_timestamp = timestamp
            return True
        return False

    def save_avatars(self):
        if self.contact.is_chatroom():
            self.group_contacts = self.database.get_chatroom_members(self.contact.wxid)
            self.group_contacts[Me().wxid] = Me()
        else:
            self.group_contacts = {
                Me().wxid: Me(),
                self.contact.wxid: self.contact
            }
        for wxid, contact in self.group_contacts.items():
            self.save_avatar(contact)

    def save_avatar(self, contact):
        avatar_buffer = self.database.get_avatar_buffer(contact.wxid)
        avatar_path = os.path.join(self.origin_path, 'avatar', f'{contact.wxid}.png')
        contact.avatar_path = avatar_path
        if not avatar_buffer:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 构建要读取的文件路径
            file_path = os.path.join(current_dir, 'resources', 'default_avatar.png')
            with open(file_path, 'rb') as f:
                avatar_buffer = f.read()
        try:
            with open(avatar_path, 'wb') as f:
                f.write(avatar_buffer)
        except:
            logger.error(traceback.format_exc())
        finally:
            return avatar_path

    def get_avatar_path(self, message: Message, is_absolute_path=False) -> str | int:
        """
        获取消息发送者的头像
        @param message: 消息元组
        @param is_absolute_path: 是否是绝对路径
        @return: True 返回本地的绝对路径，False 返回联系人的索引下标
        """
        is_send = message.is_sender
        if is_absolute_path:
            # 返回头像的本地绝对路径
            if message.sender_id in self.group_contacts:
                avatar = self.group_contacts[message.sender_id].avatar_path
            else:
                # 针对那些退群的人，就保存为默认头像
                contact = self.database.get_contact_by_username(message.sender_id)
                avatar = self.save_avatar(contact)
                self.group_contacts[contact.wxid] = contact
        else:
            if self.contact.is_chatroom():
                avatar = self.avatar_urls_dict[message.sender_id]
            else:
                avatar = 0 if is_send else 1
        return avatar

    def get_avatar_urls(self):
        index = 0
        if self.contact.is_chatroom():
            messages = msg_db.get_messages(self.contact.wxid, time_range=self.time_range)
            for message in messages:
                contact = message[13]
                if contact.wxid not in self.avatar_urls_dict:
                    avatar_path = os.path.join(self.origin_path, 'avatar', f'{contact.wxid}.png')
                    contact.save_avatar(avatar_path)
                    self.avatar_urls.append(contact.small_head_img_url)
                    self.avatar_paths.append(f'./avatar/{contact.wxid}.png')
                    self.avatar_urls_dict[contact.wxid] = index
                    index += 1
        else:
            self.avatar_urls = [Me().small_head_img_url, self.contact.small_head_img_url]
            avatar_path = os.path.join(self.origin_path, 'avatar', f'{Me().wxid}.png')
            QMe().save_avatar(avatar_path)
            avatar_path1 = os.path.join(self.origin_path, 'avatar', f'{self.contact.wxid}.png')
            # self.contact.save_avatar(avatar_path1)
            self.avatar_paths = [f'./avatar/{Me().wxid}.png', f'./avatar/{self.contact.wxid}.png']
        return self.avatar_urls, self.avatar_paths

    def get_avatar_paths(self):
        """
        获取全部头像
        @return:
        """
        index = 0
        if self.contact.is_chatroom():
            messages = msg_db.get_messages(self.contact.wxid, time_range=self.time_range)
            for message in messages:
                contact = message[13]
                if contact.wxid not in self.avatar_paths_dict:
                    self.avatar_paths.append(contact.small_head_img_url)
                    self.avatar_paths_dict[contact.wxid] = index
                    index += 1
        else:
            self.avatar_paths = [Me().small_head_img_url, self.contact.small_head_img_url]
        return self.avatar_paths


class ImageExporter(ExporterBaseBase):
    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        self.startSignal.emit(1)
        messages = database.get_messages_all()
        num = len(messages)
        os.makedirs(os.path.join(config.OUTPUT_DIR, 'image'), exist_ok=True)
        for index, message in enumerate(messages):
            type_ = message[2]
            timestamp = message[5]
            # 把时间戳转换为格式化时间
            time_struct = time.localtime(timestamp)  # 首先把时间戳转换为结构化时间
            str_time = time.strftime("%Y%m%d_%H%M%S_", time_struct)  # 把结构化时间转换为格式化时间
            MsgSvrID = str(message[9])
            if type_ == 3:
                base_path = os.path.join(config.OUTPUT_DIR, 'image')
                str_content = message[7]
                BytesExtra = message[10]
                str_content = escape_js_and_html(str_content)
                image_path = hard_link_db.get_image(str_content, BytesExtra, up_dir=Me().wx_dir, thumb=False)
                image_path = get_image(image_path, base_path=base_path, dst_name=str_time + MsgSvrID[:6])
                globalSignals.status_bar_message.emit((f'导出进度：{index + 1}/{num}——{image_path}', 1))
        self.okSignal.emit(self.id)


class VideoExporter(ExporterBaseBase):
    def run(self):
        self.startSignal.emit(1)
        messages = database.get_messages_all()
        num = len(messages)
        os.makedirs(os.path.join(config.OUTPUT_DIR, 'video'), exist_ok=True)
        for index, message in enumerate(messages):
            type_ = message[2]
            timestamp = message[5]
            # 把时间戳转换为格式化时间
            time_struct = time.localtime(timestamp)  # 首先把时间戳转换为结构化时间
            str_time = time.strftime("%Y%m%d_%H%M%S_", time_struct)  # 把结构化时间转换为格式化时间
            MsgSvrID = str(message[9])
            if type_ == 43:
                str_content = message[7]
                BytesExtra = message[10]
                video_path = hard_link_db.get_video(str_content, BytesExtra, thumb=False)
                image_path = hard_link_db.get_video(str_content, BytesExtra, thumb=True)
                if video_path:
                    video_path = f'{Me().wx_dir}/{video_path}'
                    if os.path.exists(video_path):
                        new_path = os.path.join(config.OUTPUT_DIR, 'video', str_time + MsgSvrID[:6] + '.mp4')
                        if not os.path.exists(new_path):
                            shutil.copy(video_path, new_path)
                globalSignals.status_bar_message.emit((f'导出进度：{index + 1}/{num}——{image_path}', 1))
        self.okSignal.emit(self.id)


class FileExporter(ExporterBaseBase):
    def run(self):
        self.startSignal.emit(1)
        messages = database.get_messages_all()
        num = len(messages)
        origin_path = os.path.join(config.OUTPUT_DIR, 'files')
        os.makedirs(os.path.join(config.OUTPUT_DIR, 'files'), exist_ok=True)
        for index, message in enumerate(messages):
            type_ = message[2]
            sub_type = message[3]
            timestamp = message[5]
            # 把时间戳转换为格式化时间
            time_struct = time.localtime(timestamp)  # 首先把时间戳转换为结构化时间
            str_time = time.strftime("%Y%m%d%H%M%S", time_struct)  # 把结构化时间转换为格式化时间
            if type_ == 49 and sub_type == 6:
                bytesExtra = message[10]
                compress_content = message[13]
                file_info = file(bytesExtra, compress_content, output_path=origin_path)
                if not file_info.get('is_error'):
                    file_path = file_info.get('file_path')
                    globalSignals.status_bar_message.emit((f'导出进度：{index + 1}/{num}——{file_path}', 1))
        self.okSignal.emit(self.id)


class AudioExporter(ExporterBaseBase):
    def run(self):
        self.startSignal.emit(1)
        messages = msg_db.get_messages_all()
        num = len(messages)
        for index, message in enumerate(messages):
            type_ = message[2]
            timestamp = message[5]
            # 把时间戳转换为格式化时间
            time_struct = time.localtime(timestamp)  # 首先把时间戳转换为结构化时间
            str_time = time.strftime("%Y%m%d%H%M%S", time_struct)  # 把结构化时间转换为格式化时间
            MsgSvrID = str(message[9])
            if type_ == 43:
                str_content = message[7]
                BytesExtra = message[10]
                video_path = hard_link_db.get_video(str_content, BytesExtra, thumb=False)
                image_path = hard_link_db.get_video(str_content, BytesExtra, thumb=True)
                if video_path:
                    video_path = f'{Me().wx_dir}/{video_path}'
                    if os.path.exists(video_path):
                        new_path = os.path.join(config.OUTPUT_DIR, 'video', str_time + '.mp4')
                        if not os.path.exists(new_path):
                            shutil.copy(video_path, new_path)
                globalSignals.status_bar_message.emit((f'导出进度：{index + 1}/{num}——{image_path}', 1))
        self.okSignal.emit(self.id)


class ContactExporter(ExporterBaseBase):
    def __init__(self, database, output_path):
        super().__init__()
        self.okSignal = None
        self.database = database
        self.output_path = output_path

    def start(self):
        self.run()

    def run(self):

        # columns = ["用户名", "消息内容", "发送时间", "发送状态", "消息类型", "isSend", "msgId"]
        columns = ['UserName', 'Alias', 'Type', 'Remark', 'NickName', 'smallHeadImgUrl',
                   'bigHeadImgUrl', 'label', 'gender', 'signature', 'country/region', 'province', 'city']

        contacts = self.database.get_contacts()
        try:
            # 写入CSV文件
            with open(self.output_path, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(columns)
                # 写入数据
                for contact in contacts:
                    writer.writerow(
                        [contact.wxid, contact.alias, contact.flag, contact.remark, contact.nickname,
                         contact.small_head_img_url, contact.big_head_img_url, contact.label_name(), contact.gender,
                         contact.signature, *contact.region
                         ]
                    )
        except PermissionError:
            print('另一个程序正在使用此文件，无法访问。')


class GroupContactExporter(ExporterBaseBase):
    def __init__(self, database, output_dir, contact):
        super().__init__()
        self.contact = contact
        self.database = database
        if self.contact:
            if not isinstance(self.contact, list):
                self.origin_path = os.path.join(output_dir, '聊天记录',
                                                f'{self.contact.remark}({self.contact.wxid})')
                os.makedirs(self.origin_path, exist_ok=True)

    def start(self):
        self.run()

    def run(self):
        filename = os.path.join(self.origin_path, 'contacts.csv')
        filename = get_new_filename(filename)
        # columns = ["用户名", "消息内容", "发送时间", "发送状态", "消息类型", "isSend", "msgId"]
        columns = ['UserName', '微信号', '类型', '群昵称', '昵称', '头像地址',
                   '头像原图', '标签', '性别', '个性签名', '国家（地区）', '省份', '城市']
        contacts = self.database.get_chatroom_members(self.contact.wxid)
        try:
            # 写入CSV文件
            with open(filename, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(columns)
                # 写入数据
                # writer.writerows(contacts)
                for wxid, contact in contacts.items():
                    writer.writerow(
                        [
                            contact.wxid, contact.alias, contact.flag, contact.remark, contact.nickname,
                            contact.small_head_img_url, contact.big_head_img_url, contact.label_name(),
                            contact.gender, contact.signature, *contact.region
                        ]
                    )
        except PermissionError:
            print('另一个程序正在使用此文件，无法访问。')


class CsvAllExporter(ExporterBaseBase):
    def run(self):
        filename = QFileDialog.getSaveFileName(None, "save file", os.path.join(os.getcwd(), 'messages.csv'),
                                               "csv files (*.csv);;all files(*.*)")
        if not filename[0]:
            return
        self.startSignal.emit(1)
        filename = filename[0]
        # columns = ["用户名", "消息内容", "发送时间", "发送状态", "消息类型", "isSend", "msgId"]
        columns = ['localId', 'TalkerId', 'Type', 'SubType',
                   'IsSender', 'CreateTime', 'Status', 'StrContent',
                   'StrTime', 'Remark', 'NickName', 'Sender']

        packagemsg = PackageMsg()
        messages = packagemsg.get_package_message_all()
        try:
            # 写入CSV文件
            with open(filename, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(columns)
                # 写入数据
                writer.writerows(messages)
        except PermissionError:
            globalSignals.information.emit('另一个程序正在使用此文件，无法访问。')
        self.okSignal.emit(self.id)


def copy_file(source_file, destination_file):
    if os.path.isfile(source_file) and not os.path.exists(destination_file):
        try:
            # logger.info(f'开始复制:{destination_file}')
            shutil.copy(source_file, destination_file)
        except:
            pass
            # logger.error(traceback.format_exc())
        finally:
            print(f'复制:{destination_file}')
            # logger.info(f'复制:{destination_file}')


def copy_files(file_tasks: List[Tuple[str, str, str]]):
    """

    :param file_tasks: List[
        (原始文件路径,
            输出文件夹,
            输出文件名
            )]
    :return:
    """
    if len(file_tasks) < 1:
        return
    futures = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for source_file, output_dir, dst_name in file_tasks:
            if dst_name:
                ext = os.path.basename(source_file).split('.')[-1]
                destination_file = os.path.join(output_dir, f'{dst_name}.{ext}')
            else:
                destination_file = os.path.join(output_dir, os.path.basename(source_file))
            if os.path.exists(destination_file):
                continue
            if not os.path.exists(os.path.dirname(destination_file)):
                os.makedirs(os.path.dirname(destination_file), exist_ok=True)
            futures.append(executor.submit(copy_file, source_file, destination_file))

            # 等待所有任务完成
            for future in futures:
                future.result()


def get_ffmpeg_path():
    # 获取打包后的资源目录
    resource_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))

    # 构建 FFmpeg 可执行文件的路径
    ffmpeg_path = os.path.join(resource_dir, 'ffmpeg.exe')
    if not os.path.exists(ffmpeg_path):
        ffmpeg_path = os.path.join(resource_dir, 'resources', 'ffmpeg.exe')
    return ffmpeg_path


def decode_audio_to_mp3(media_buffer, output_dir, filename):
    silk_path = f"{output_dir}/{filename}.silk"
    pcm_path = f"{output_dir}/{filename}.pcm"
    mp3_path = f"{output_dir}/{filename}.mp3"
    if os.path.exists(mp3_path):
        return mp3_path
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    buf = media_buffer
    if not buf:
        return ''
    with open(silk_path, "wb") as f:
        f.write(buf)
    # open(silk_path, "wb").write()
    try:
        pcm_buf = pysilk.decode(buf, to_wav=False, sample_rate=44100)
        with open(pcm_path, 'wb') as f:
            f.write(pcm_buf)
        # pysilk.decode_file(open("brainpower.pcm", "rb"), to_wav=False)
        # 调用系统上的 ffmpeg 可执行文件
        # 获取 FFmpeg 可执行文件的路径
        ffmpeg_path = get_ffmpeg_path()
        # print(ffmpeg_path)
        # # 调用 FFmpeg
        if os.path.exists(ffmpeg_path):
            cmd = f'''"{ffmpeg_path}" -loglevel quiet -y -f s16le -i "{pcm_path}" -ar 44100 -ac 1 "{mp3_path}"'''
            # system(cmd)
            # 使用subprocess.run()执行命令
            subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            # 源码运行的时候下面的有效
            # 这里不知道怎么捕捉异常
            cmd = f'''"{os.path.join(os.getcwd(), 'app', 'resources', 'data', 'ffmpeg.exe')}" -loglevel quiet -y -f s16le -i "{pcm_path}" -ar 44100 -ac 1 "{mp3_path}"'''
            # system(cmd)
            # 使用subprocess.run()执行命令
            subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # if os.path.exists(silk_path):
        #     os.remove(silk_path)
        # if os.path.exists(pcm_path):
        #     os.remove(pcm_path)
    except Exception as e:
        print(f"Error: {e}")
        logger.error(f'语音错误\n{traceback.format_exc()}')
        cmd = f'''"{os.path.join(os.getcwd(), 'app', 'resources', 'data', 'ffmpeg.exe')}" -loglevel quiet -y -f s16le -i "{pcm_path}" -ar 44100 -ac 1 "{mp3_path}"'''
        # system(cmd)
        # 使用subprocess.run()执行命令
        subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        return mp3_path


def decode_audios(file_tasks: List[Tuple[str, str, str]]):
    """

    :param database:
    :param file_tasks: List[
        (原始文件路径,
            输出文件夹,
            输出文件名
            )]
    :return:
    """
    if len(file_tasks) < 1:
        return
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for media_buffer, output_dir, dst_name in file_tasks:
            futures.append(executor.submit(decode_audio_to_mp3, media_buffer, output_dir, dst_name))

        # 等待所有任务完成
        for future in futures:
            future.result()


def remove_privacy_info(text):
    # 正则表达式模式
    patterns = {
        'phone': r'\b(\+?86[-\s]?)?1[3-9]\d{9}\b',  # 手机号
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # 邮箱
        'id_card': r'\b\d{15}|\d{18}|\d{17}X\b',  # 身份证号
        'password': r'\b(?:password|pwd|pass|psw)[\s=:]*\S+\b',  # 密码
        'account': r'\b(?:account|username|user|acct)[\s=:]*\S+\b'  # 账号
    }

    for key, pattern in patterns.items():
        text = re.sub(pattern, f'[{key} xxx]', text)

    return text


def get_new_filename(filename):
    """
    检查给定的文件是否存在，如果存在就加个括号标个号，返回新的文件名
    @param filename:
    @return:
    """
    if not os.path.exists(filename):
        return filename
    else:
        for i in range(1, 10086):
            basename = os.path.basename(filename)
            tmp = basename.split('.')
            name = '.'.join(tmp[:-1])
            ext = tmp[-1]
            dir_name = os.path.dirname(filename)
            new_filename = os.path.join(dir_name, f'{name}({i}).{ext}')
            if not os.path.exists(new_filename):
                return new_filename
    return filename
