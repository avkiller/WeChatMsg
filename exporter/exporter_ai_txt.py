import os
import re
from collections import defaultdict

from wxManager import Message
from exporter.exporter import ExporterBase, get_new_filename, remove_privacy_info


class AiTxtExporter(ExporterBase):
    last_sender = 'wxid_00112233'

    def title(self, message: Message):
        sender = message.sender_id
        display_name = ''
        if sender != self.last_sender:
            display_name = f'\n{message.display_name}:'
        self.last_sender = sender
        return display_name

    def export(self):
        # 实现导出为txt的逻辑
        print(f"【开始导出 TXT {self.contact.remark}】")
        origin_path = self.origin_path
        os.makedirs(origin_path, exist_ok=True)
        filename = os.path.join(origin_path, self.contact.remark + '_chat.txt')
        filename = get_new_filename(filename)
        messages = self.database.get_messages(self.contact.wxid, time_range=self.time_range)
        total_steps = len(messages)
        # 创建一个默认字典，用于按日期分组
        grouped_messages = defaultdict(list)
        # 遍历消息，将其按日期分组
        for index, message in enumerate(messages):
            if index and index % 1000 == 0:
                self.update_progress_callback(index / total_steps)
            if not self.is_selected(message):
                continue
            date_key = message.str_time[:10]  # 以日期作为键
            # 将消息添加到对应日期的列表中
            grouped_messages[date_key].append(f'{self.title(message)}{remove_privacy_info(message.to_text())}')

        with open(filename, mode='w', newline='', encoding='utf-8') as f:
            # 如果需要，可以将结果转换为普通字典
            grouped_messages = dict(grouped_messages)
            # 按日期排序并遍历结果
            for date in sorted(grouped_messages.keys()):
                msgs = grouped_messages[date]
                f.write(f"\n\n{'*' * 20}{date}{'*' * 20}\n")
                f.write('\n'.join(msgs))
        self.update_progress_callback(1)
        print(f"【完成导出 TXT {self.contact.remark}】")
        self.finish_callback(self.exporter_id)
