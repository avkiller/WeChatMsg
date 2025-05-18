import csv
import os

from wxManager import Message
from wxManager.model import Me
from exporter.exporter import ExporterBase, get_new_filename


class CSVExporter(ExporterBase):
    def message_to_list(self, message: Message):
        remark = message.display_name
        nickname = message.display_name
        if self.contact.is_chatroom():
            contact = self.group_contacts.get(message.sender_id)
            if contact:
                remark = contact.remark
                nickname = contact.nickname
        else:
            contact = Me() if message.is_sender else self.contact
            remark = contact.remark
            nickname = contact.nickname
        res = [str(message.server_id), message.type_name(), message.display_name, message.str_time, message.to_text(),
               remark, nickname, 'more']
        return res

    def export(self):
        print(f"【开始导出 CSV {self.contact.remark}】")
        os.makedirs(self.origin_path, exist_ok=True)
        filename = os.path.join(self.origin_path,f"{self.contact.remark}.csv")
        filename = get_new_filename(filename)
        columns = ['消息ID', '类型', '发送人', '时间', '内容', '备注', '昵称', '更多信息']
        messages = self.database.get_messages(self.contact.wxid, time_range=self.time_range)
        total_steps = len(messages)
        # 写入CSV文件
        with open(filename, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow(columns)
            # 写入数据
            csv_res = []
            for index, message in enumerate(messages):
                if index and index % 1000 == 0:
                    self.update_progress_callback(index / total_steps)
                if not self.is_selected(message):
                    continue
                csv_res.append(self.message_to_list(message))
            writer.writerows(csv_res)
        self.update_progress_callback(1)
        self.finish_callback(self.exporter_id)
        print(f"【完成导出 CSV {self.contact.remark}】")
