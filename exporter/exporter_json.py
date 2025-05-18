import json
import random
import os

from wxManager import Me, MessageType
from exporter.exporter import ExporterBase, remove_privacy_info, get_new_filename


class JsonStrategy:
    SPLIT_BY_TIME = 0  # 距离第一条消息的时间范围
    SPLIT_BY_INTERVALS = 1  # 相邻消息的时间间隔
    SLIDING_WINDOW = 2  # 滑动窗口法分割


class AssistantUser:
    SELF = 0  # 自己是ai助手
    CONTACT = 1  # 好友是ai助手


class JsonConfig:
    prompt: str = ''
    shuffle: bool = True  # 是否随机打乱数据
    train_ratio: int = 80  # 训练集占比（百分比）
    model: str = 'Alpaca'  # 可选：GLM4，ChatGLM3
    model_keys = {
        'GLM4': 'messages',
        'ChatGLM3': 'conversations'
    }
    strategy: int = JsonStrategy.SPLIT_BY_INTERVALS  # json导出策略
    intervals: int = 120  # 相邻两条消息的最大间隔时间
    span: int = 300  # 第一条消息跟最后一条消息的间隔时间
    window_size: int = 10  # 窗口大小
    step: int = 3  # 步长
    assistant = AssistantUser.SELF

    def get_model_keys(self):
        return self.model_keys.get(self.model, 'messages')


def modify(output, history):
    return output


def merge_content(conversions_list) -> list:
    """
    合并一组对话中连续发送的句子
    @param conversions_list:
    @return:
    """
    merged_data = []
    current_role = None
    current_content = ""
    str_time = ''
    for item in conversions_list:
        if 'str_time' in item:
            str_time = item['str_time']
        else:
            str_time = ''
        if current_role is None:
            current_role = item["role"]
            current_content = item["content"]
        elif current_role == item["role"]:
            current_content += "，" + item["content"]
        else:
            # merged_data.append({"role": current_role, "content": current_content, 'str_time': str_time})
            if len(current_content) < 3 and current_role == 'assistant':
                current_content = modify(current_content, merged_data)
            merged_data.append({"role": current_role, "content": current_content})
            current_role = item["role"]
            current_content = item["content"]
            str_time = item.get('str_time')

    # 处理最后一组
    if current_role is not None:
        # merged_data.append({"role": current_role, "content": current_content,'str_time': str_time})
        merged_data.append({"role": current_role, "content": current_content})
    return merged_data


def is_first_msg(conversions):
    if not conversions:
        return True
    else:
        return len(conversions) == 1 and conversions[0]['role'] == 'system'


def conversion_to_history(conversations):
    res = []
    has_system_prompt = conversations[0].get('role') == 'system'
    s_index, e_index = (1, len(conversations) - 3) if has_system_prompt else (0, len(conversations) - 2)
    for i in range(s_index, e_index, 2):
        res.append(
            [
                conversations[i].get('content'), conversations[i + 1].get('content')
            ]
        )
    return res


class JsonExporter(ExporterBase):
    def __init__(
            self,
            database,
            contact,
            output_dir,
            type_,  # 导出文件类型
            message_types: set[MessageType] = None,  # 导出的消息类型
            time_range=None,  # 导出的日期范围
            group_members: set[str] = None,  # 群聊中只导出这些人的聊天记录
            progress_callback=None,  # 进度回调函数，func(progress:float)
            finish_callback=None,  # 导出完成回调函数
            json_config: JsonConfig = None
    ):
        super().__init__(database, contact, output_dir, type_, message_types, time_range, group_members,
                         progress_callback, finish_callback)  # 调用父类的构造函数
        if json_config:
            self.json_config: JsonConfig = json_config
        else:
            self.json_config = JsonConfig()

    def is_user(self, is_send):
        """
        判断一条消息是否是user角色发送的
        @param is_send:
        @return:
        """
        return is_send ^ (self.json_config.assistant == AssistantUser.SELF)

    def system_prompt(self):
        system = {
            "role": "system",
            "content": self.json_config.prompt.replace(
                '{{name}}', Me().name
            ).replace(
                '{{remark}}', self.contact.remark
            )
        }
        return system

    def message_to_conversion(self, group):
        conversions = [self.system_prompt()] if self.json_config.prompt else []
        # 确保最后一条消息是assistant发出的
        while len(group) and self.is_user(group[-1].is_sender):
            group.pop()
        for message in group:
            is_send = message.is_sender
            text = remove_privacy_info(message.content)
            # 确保第一条消息必须是user发出的
            if is_first_msg(conversions) and not self.is_user(is_send):
                continue
            if self.is_user(is_send):
                json_msg = {
                    "role": "user",
                    "content": text
                }
            else:
                json_msg = {
                    "role": "assistant",
                    "content": text
                }
            json_msg['str_time'] = message.str_time
            conversions.append(json_msg)
        if len(conversions) == 1:
            return []
        return merge_content(conversions)

    def split_by_time(self, length=300):
        """
        通过第一条消息和最后一条消息的时间间隔分割数据集
        @param length:
        @return:
        """
        messages = self.database.get_messages_by_type(self.contact.wxid, type_=MessageType.Text,
                                                      time_range=self.time_range)
        start_time = 0
        res = []
        i = 0
        while i < len(messages):
            message = messages[i]
            timestamp = message.timestamp
            is_send = message.is_sender
            group = []
            while i < len(messages) and timestamp - start_time < length:
                group.append(message)
                i += 1
                if i >= len(messages):
                    break
                message = messages[i]
                timestamp = message.timestamp
                is_send = message.is_sender
            while not self.is_user(is_send):
                group.append(message)
                i += 1
                if i >= len(messages):
                    break
                message = messages[i]
                timestamp = message.timestamp
                is_send = message.is_sender
            start_time = timestamp
            if len(group) > 4:
                res.append(group)
        return res

    def split_by_intervals(self, max_diff_seconds=300):
        """
        通过相邻两条消息的时间间隔分割数据集
        @param max_diff_seconds:
        @return:
        """
        messages = self.database.get_messages_by_type(self.contact.wxid, type_=MessageType.Text,
                                                      time_range=self.time_range)
        res = []
        i = 0
        current_group = []
        while i < len(messages):
            message = messages[i]
            timestamp = message.timestamp
            is_send = message.is_sender
            while not self.is_user(is_send) and i + 1 < len(messages):
                i += 1
                message = messages[i]
                is_send = message.is_sender
            current_group = [messages[i]]
            i += 1
            while i < len(messages) and messages[i].timestamp - current_group[-1].timestamp <= max_diff_seconds:
                current_group.append(messages[i])
                i += 1
            while i < len(messages) and not self.is_user(messages[i].is_sender):
                current_group.append(messages[i])
                i += 1
            if len(current_group) > 4:
                res.append(current_group)
        return res

    def split_by_window(self, window_size=10, step=3):
        """
        滑动窗口切分数据集
        @param window_size:
        @param step:
        @return:
        """
        messages = self.database.get_messages_by_type(self.contact.wxid, type_=MessageType.Text,
                                                      time_range=self.time_range)
        res = []
        i = 0
        while i < len(messages):
            message = messages[i]
            timestamp = message.timestamp
            is_send = message.is_sender
            current_group = []
            j = i
            while not self.is_user(is_send) and j + 1 < len(messages) and j - i < window_size:
                j += 1
                message = messages[j]
                is_send = message.is_sender
            current_group = [messages[j]]
            j += 1
            while j < len(messages) and j - i < window_size:
                current_group.append(messages[j])
                j += 1
            res.append(current_group)
            i += step
        return res

    def export(self):
        print(f"【开始导出 json {self.contact.remark}】")
        origin_path = self.origin_path
        filename = os.path.join(origin_path, f"{self.contact.remark}.json")
        filename = get_new_filename(filename)
        messages_groups = []
        match self.json_config.strategy:
            case JsonStrategy.SPLIT_BY_INTERVALS:
                messages_groups = self.split_by_intervals(self.json_config.intervals)
            case JsonStrategy.SPLIT_BY_TIME:
                messages_groups = self.split_by_time(self.json_config.span)
            case JsonStrategy.SLIDING_WINDOW:
                messages_groups = self.split_by_window(self.json_config.window_size, self.json_config.step)
        dataset = []
        self.update_progress_callback(0.5)
        for group in messages_groups:
            conversations = self.message_to_conversion(group)
            if conversations:
                if self.json_config.model == 'Alpaca':
                    has_system_prompt = conversations[0].get('role') == 'system'
                    dataset.append(
                        {
                            'system': conversations[0].get('content') if has_system_prompt else '',
                            'instruction': conversations[-2].get('content'),
                            'input': '',
                            'output': conversations[-1].get('content'),
                            'history': conversion_to_history(conversations),
                        }
                    )
                else:
                    dataset.append({
                        self.json_config.get_model_keys(): conversations
                    })
        if self.json_config.shuffle:
            # 打乱列表顺序
            random.shuffle(dataset)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=4)
        print(f"【完成导出 json {self.contact.remark}】")
        self.update_progress_callback(1)
        self.finish_callback(self.exporter_id)
