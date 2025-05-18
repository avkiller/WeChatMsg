import copy
import html
import json
import math
import os
import shutil
import time
from wxManager.decrypt.decrypt_dat import batch_decode_image_multiprocessing
from wxManager.log import logger
from wxManager.model import MessageType, Me
from exporter.exporter import ExporterBase, copy_files, decode_audios, get_new_filename

icon_files = {
    'DOCX': ['doc', 'docx'],
    'XLS': ['xls', 'xlsx'],
    'CSV': ['csv'],
    'TXT': ['txt'],
    'ZIP': ['zip', '7z', 'rar'],
    'PPT': ['ppt', 'pptx'],
    'PDF': ['pdf'],
}


class HtmlExporter(ExporterBase):

    def export(self):
        print(f"【开始导出 HTML {self.contact.remark}】")
        f_name = '.html'
        filename = os.path.join(self.origin_path, f'{self.contact.remark}{f_name}')
        filename = get_new_filename(filename)
        # 获取当前脚本的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建要读取的文件路径
        file_path = os.path.join(current_dir, 'resources', 'template.html')
        shutil.copytree(os.path.join(current_dir, 'resources', 'emoji'), os.path.join(self.origin_path, 'emoji'),dirs_exist_ok=True)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            html_head, html_end = content.split('/*注意看这是分割线*/')
        f = open(filename, 'w', encoding='utf-8')
        html_head = html_head.replace("<title>出错了</title>", f"<title>{self.contact.remark}</title>")
        html_head = html_head.replace("<p id=\"title\">出错了</p>", f"<p id=\"title\">{self.contact.remark}</p>")
        # avatar_urls, avatar_paths = self.get_avatar_urls()
        avatar_urls = []
        avatar_paths = []
        html_head = html_head.replace("{{avatarPaths}}", json.dumps(avatar_paths))
        html_head = html_head.replace("{{avatarUrls}}", json.dumps(avatar_urls)).replace('{{wxid}}',
                                                                                         f'"{self.contact.wxid}"')
        f.write(html_head)
        messages = self.database.get_messages(self.contact.wxid, time_range=self.time_range)

        # QMe().save_avatar(self.origin_path + '/avatar/' + Me().wxid + '.png')
        # self.contact.save_avatar(self.origin_path + '/avatar/' + self.contact.wxid + '.png')
        date_id_map = {}
        timelineData = {}
        PageTimeline = {}
        server_id_Page = {}
        server_id_Idx = {}

        AllIndex = []
        ImageIndex = []
        FileIndex = []
        LinkIndex = []
        MusicIndex = []
        TransferIndex = []
        MiniProgramIndex = []
        VideoNumberIndex = []
        dateDataMap = {}
        i = 0
        itemsPerPage = 100
        num = 1
        html_json = []
        image_tasks = []
        video_tasks = []
        file_tasks = []
        audio_tasks = []
        image_dir = os.path.join(self.origin_path, 'image')
        video_dir = os.path.join(self.origin_path, 'video')
        audio_dir = os.path.join(self.origin_path, 'voice')
        file_dir = os.path.join(self.origin_path, 'file')
        total_steps = len(messages)
        select_msg_cnt = 0  # 要导出的消息数量
        msg_index = 0

        def parser_merged(merged_message):
            for msg in merged_message.messages:
                type_ = msg.type
                if type_ == MessageType.Image:
                    msg.set_file_name()
                    image_tasks.append(
                        (
                            os.path.join(Me().wx_dir, msg.path),
                            os.path.join(image_dir, msg.str_time[:7]),
                            msg.file_name
                        )
                    )
                    image_tasks.append(
                        (
                            os.path.join(Me().wx_dir, msg.thumb_path),
                            os.path.join(image_dir, msg.str_time[:7]),
                            msg.file_name + '_t'
                        )
                    )
                    msg.path = f"./image/{msg.str_time[:7]}/{msg.file_name}"
                    msg.thumb_path = f"./image/{msg.str_time[:7]}/{msg.file_name + '_t'}"
                elif type_ == MessageType.File:
                    origin_file_path = os.path.join(Me().wx_dir, msg.path)
                    file_tasks.append(
                        (
                            origin_file_path,
                            os.path.join(file_dir, msg.str_time[:7]),
                            ''
                        )
                    )
                    msg.path = f'./file/{msg.str_time[:7]}/{os.path.basename(origin_file_path)}'
                elif type_ == MessageType.Video:
                    msg.set_file_name()
                    video_tasks.append(
                        (
                            os.path.join(Me().wx_dir, msg.path),
                            os.path.join(video_dir, msg.str_time[:7]),
                            msg.file_name
                        )
                    )
                    ext = os.path.basename(msg.path).split('.')[-1]
                    msg.path = f'./video/{msg.str_time[:7]}/{msg.file_name}.{ext}'
                elif type_ == MessageType.MergedMessages:
                    parser_merged(msg)

        for index, message in enumerate(messages):
            if not self._is_running:
                break
            if index and index % 1000 == 0:
                self.update_progress_callback(index / total_steps)
            type_ = message.type
            if not self.is_selected(message):
                continue
            server_id = message.server_id
            if type_ == MessageType.Image:
                ImageIndex.append(msg_index)
                message.set_file_name()
                image_tasks.append(
                    (
                        os.path.join(Me().wx_dir, message.path),
                        os.path.join(image_dir, message.str_time[:7]),
                        message.file_name
                    )
                )
                image_tasks.append(
                    (
                        os.path.join(Me().wx_dir, message.thumb_path),
                        os.path.join(image_dir, message.str_time[:7]),
                        message.file_name + '_t'
                    )
                )
                message.path = f"./image/{message.str_time[:7]}/{message.file_name}"
                message.thumb_path = f"./image/{message.str_time[:7]}/{message.file_name + '_t'}"
            elif type_ == MessageType.File:
                FileIndex.append(msg_index)
                origin_file_path = os.path.join(Me().wx_dir, message.path)
                file_tasks.append(
                    (
                        origin_file_path,
                        os.path.join(file_dir, message.str_time[:7]),
                        ''
                    )
                )
                if os.path.isfile(origin_file_path):
                    message.path = f'./file/{message.str_time[:7]}/{os.path.basename(origin_file_path)}'
            elif type_ == MessageType.Video:
                ImageIndex.append(msg_index)
                message.set_file_name()
                video_tasks.append(
                    (
                        os.path.join(Me().wx_dir, message.path),
                        os.path.join(video_dir, message.str_time[:7]),
                        message.file_name
                    )
                )
                ext = os.path.basename(message.path).split('.')[-1]
                message.path = f'./video/{message.str_time[:7]}/{message.file_name}.{ext}'
            elif type_ == MessageType.Audio:
                message.set_file_name()
                audio_tasks.append(
                    (
                        self.database.get_media_buffer(message.server_id, self.contact.is_public()),
                        os.path.join(audio_dir, message.str_time[:7]),
                        message.file_name
                    )
                )
                message.path = f'./voice/{message.str_time[:7]}/{message.file_name + ".mp3"}'
            elif type_ == MessageType.LinkMessage or type_ == MessageType.LinkMessage2 or type_ == MessageType.LinkMessage4 or type_ == MessageType.LinkMessage5 or type_ == MessageType.LinkMessage6:
                LinkIndex.append(msg_index)
            elif type_ == MessageType.Music:
                MusicIndex.append(msg_index)
            elif type_ == MessageType.Transfer:
                TransferIndex.append(msg_index)
            elif type_ == MessageType.Applet or type_ == MessageType.Applet2:
                MiniProgramIndex.append(msg_index)
            elif type_ == MessageType.WeChatVideo:
                VideoNumberIndex.append(msg_index)
            elif type_ == MessageType.MergedMessages:
                parser_merged(message)
            msg_index += 1
            is_select = True
            html_json.append(message.to_json())
            if is_select:
                select_msg_cnt += 1
                # 把时间戳转换为格式化时间
                str_time = message.str_time
                # 2024-01-01
                year = str_time[:4]
                month = int(str_time[5:7])
                curpage = math.ceil(select_msg_cnt / itemsPerPage)
                if str_time[:10] not in date_id_map:
                    date_id_map[str_time[:10]] = str(server_id)
                if str_time[:10] not in dateDataMap:
                    dateDataMap[str_time[:10]] = [curpage, str(server_id)]

                if year not in timelineData:
                    timelineData[year] = {}
                if month not in timelineData[year]:
                    timelineData[year][month] = []
                    timelineData[year][month].append(curpage)
                    timelineData[year][month].append(str(server_id))

                if curpage not in PageTimeline:
                    PageTimeline[curpage] = {}
                    PageTimeline[curpage]['year'] = year
                    PageTimeline[curpage]['month'] = month

                server_id_Page[str(server_id)] = curpage
                server_id_Idx[str(server_id)] = select_msg_cnt - 1

        # print(image_tasks)
        # print(file_tasks)
        # print(video_tasks)
        # print(audio_tasks)
        logger.info('解析图片')
        # 使用多进程，导出所有图片
        batch_decode_image_multiprocessing(Me().xor_key, image_tasks)
        print('开始复制文件')
        logger.info(f'开始复制{len(video_tasks + file_tasks)}')
        # 使用多线程，复制文件、视频到导出文件夹
        copy_files(video_tasks + file_tasks)
        print('开始导出语音')
        logger.info('开始导出语音')
        decode_audios(audio_tasks)

        AllIndex = list(range(len(html_json)))

        replace_map = {
            "{{timelineData}}": timelineData,
            "{{PageTimeline}}": PageTimeline,
            "{{server_id_Page}}": server_id_Page,
            "{{server_id_Idx}}": server_id_Idx,
            "{{dateDataMap}}": dateDataMap,
            "{{AllIndex}}": AllIndex,
            "{{ImageIndex}}": ImageIndex,
            "{{FileIndex}}": FileIndex,
            "{{LinkIndex}}": LinkIndex,
            "{{MusicIndex}}": MusicIndex,
            "{{TransferIndex}}": TransferIndex,
            "{{MiniProgramIndex}}": MiniProgramIndex,
            "{{VideoNumberIndex}}": VideoNumberIndex
        }

        def dict_to_js(dic: dict):
            for key, value in dic.items():
                if isinstance(value, str):
                    if value.startswith('http'):
                        dic[key] = value
                    else:
                        dic[key] = html.escape(value)
                elif isinstance(value, dict):
                    dic[key] = dict_to_js(value)
            return dic

        print('开始字符串转义')
        logger.info('开始字符串转义')
        # 字符串转义，防止JS出现语法错误
        html_data = []
        for item in copy.deepcopy(html_json):
            html_data.append(dict_to_js(item))

        f.write(json.dumps(html_data, ensure_ascii=False, indent=4))
        for key, value in replace_map.items():
            html_end = html_end.replace(key, json.dumps(value))

        f.write(html_end)
        f.close()

        with open(filename + '.json', 'w', encoding='utf-8') as f:
            json.dump(html_json, f, ensure_ascii=False, indent=4)

        self.update_progress_callback(1)
        print(f"【完成导出 HTML {self.contact.remark}】{len(messages)}")
        self.finish_callback(self.exporter_id)
