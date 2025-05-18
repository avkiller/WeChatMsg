import os
import traceback

from wxManager import MessageType
from wxManager.model import Message
from exporter.exporter import ExporterBase, get_new_filename


class TxtExporter(ExporterBase):
    def title(self, message: Message):
        str_time = message.str_time
        if message.type == MessageType.System:
            return f'{str_time}'
        display_name = message.display_name
        return f'{str_time} {display_name}'

    def export(self):
        # 实现导出为txt的逻辑
        print(f"【开始导出 TXT {self.contact.remark}】")
        origin_path = self.origin_path
        os.makedirs(origin_path, exist_ok=True)
        filename = os.path.join(origin_path, self.contact.remark + '.txt')
        filename = get_new_filename(filename)
        messages = self.database.get_messages(self.contact.wxid, time_range=self.time_range)
        total_steps = len(messages)
        txt_res = []
        for index, message in enumerate(messages):
            if index and index % 1000 == 0:
                self.update_progress_callback(index / total_steps)
            if not self.is_selected(message):
                continue
            txt_res.append(f'{self.title(message)}\n{message.to_text()}')
        with open(filename, mode='w', newline='', encoding='utf-8') as f:
            f.write('\n\n'.join(txt_res))
        self.update_progress_callback(1)
        print(f"【完成导出 TXT {self.contact.remark}】")
        self.finish_callback(self.exporter_id)
