import os.path
import shutil
import subprocess
import sys
import traceback
import sqlite3
import base64

import xml.etree.ElementTree as ET

from wxManager.merge import increase_data
from wxManager.log import logger
from wxManager.model import DataBaseBase


def get_ffmpeg_path():
    # 获取打包后的资源目录
    resource_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))

    # 构建 FFmpeg 可执行文件的路径
    ffmpeg_path = os.path.join(resource_dir, 'app', 'resources', 'data', 'ffmpeg.exe')

    return ffmpeg_path


class MediaMsg(DataBaseBase):
    voice_visited = {}

    def get_media_buffer(self, reserved0):
        sql = '''
            select Buf
            from Media
            where Reserved0 = ?
        '''
        for db in self.DB:
            cursor = db.cursor()
            cursor.execute(sql, [reserved0])
            result = cursor.fetchone()
            if result:
                return result[0]
        return None

    def get_audio(self, reserved0, output_path, filename=''):
        if not filename:
            filename = reserved0
        silk_path = f"{output_path}/{filename}.silk"
        pcm_path = f"{output_path}/{filename}.pcm"
        mp3_path = f"{output_path}/{filename}.mp3"
        if os.path.exists(mp3_path):
            return mp3_path
        buf = self.get_media_buffer(reserved0)
        if not buf:
            return ''
        with open(silk_path, "wb") as f:
            f.write(buf)
        # open(silk_path, "wb").write()
        try:
            decode(silk_path, pcm_path, 44100)
            # 调用系统上的 ffmpeg 可执行文件
            # 获取 FFmpeg 可执行文件的路径
            ffmpeg_path = get_ffmpeg_path()
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
            if os.path.exists(silk_path):
                os.remove(silk_path)
            if os.path.exists(pcm_path):
                os.remove(pcm_path)
        except Exception as e:
            print(f"Error: {e}")
            logger.error(f'语音发送错误\n{traceback.format_exc()}')
            cmd = f'''"{os.path.join(os.getcwd(), 'app', 'resources', 'data', 'ffmpeg.exe')}" -loglevel quiet -y -f s16le -i "{pcm_path}" -ar 44100 -ac 1 "{mp3_path}"'''
            # system(cmd)
            # 使用subprocess.run()执行命令
            subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            return mp3_path

    def get_audio_path(self, reserved0, output_path, filename=''):
        if not filename:
            filename = reserved0
        mp3_path = f"{output_path}\\{filename}.mp3"
        mp3_path = mp3_path.replace("/", "\\")
        return mp3_path

    def get_audio_text(self, content):
        try:
            root = ET.fromstring(content)
            transtext = root.find(".//voicetrans").get("transtext")
            return transtext
        except:
            return ""

    def audio_to_text(self, token, reserved0, output_path, open_im=False, filename=''):
        buf = self.get_media_buffer(reserved0, open_im)
        if not buf:
            return ''
        if not filename:
            filename = reserved0
        silk_path = f"{output_path}/{filename}.silk"
        pcm_path = f"{output_path}/{filename}.pcm"
        with open(silk_path, "wb") as f:
            f.write(buf)
        decode(silk_path, pcm_path, 16000)
        speech_data = []
        with open(pcm_path, 'rb') as speech_file:
            speech_data = speech_file.read()
        length = len(speech_data)
        if length == 0:
            logger.error('file %s length read 0 bytes' % pcm_path)
            pass
        speech = base64.b64encode(speech_data).decode('utf-8')
        params = {'dev_pid': DEV_PID,
                  'format': 'pcm',
                  'rate': RATE,
                  'token': token,
                  'cuid': CUID,
                  'channel': 1,
                  'speech': speech,
                  'len': length
                  }
        try:
            os.remove(silk_path)
            os.remove(pcm_path)
            resp = requests.post(ASR_URL, json=params)
            if resp.status_code == 200:
                result_dict = resp.json()
                if result_dict['err_no'] == 0:
                    return result_dict['result']
                else:
                    print(result_dict)
                    return ""
            else:
                return ""
        except:
            logger.error(traceback.format_exc())
            return ""

    def merge(self, db_file_name):
        def task_(db_path, cursor, db):
            """
            每个线程执行的任务，获取某个数据库实例中的查询结果。
            """
            increase_data(db_path, cursor, db, 'Media', 'Reserved0', 1)

        tasks = []
        for i in range(100):
            db_path = db_file_name.replace('0', f'{i}')
            if os.path.exists(db_path):
                # print('初始化数据库：', db_path)
                file_name = os.path.basename(db_path)
                if file_name in self.db_file_name:
                    index = self.db_file_name.index(file_name)
                    db = self.DB[index]
                    cursor = db.cursor()
                    task_(db_path, cursor, db)
                    tasks.append([db_path, cursor, db])
                else:
                    shutil.copy(db_path, os.path.join(self.db_dir, 'Multi', file_name))
        # print(tasks)
        # 使用线程池 (没有加快合并速度)
        # with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        #     executor.map(lambda args: task_(*args), tasks)
        self.commit()
        print(len(tasks))


class Audio2TextDB:
    def __init__(self):
        self.DB = None
        self.cursor: sqlite3.Cursor = None
        self.open_flag = False
        self.init_database()

    def init_database(self, db_dir=''):
        if not self.open_flag:
            if os.path.exists(audio2text_db_path):
                self.DB = sqlite3.connect(audio2text_db_path, check_same_thread=False)
                # '''创建游标'''
                self.cursor = self.DB.cursor()
                self.open_flag = True
                if audio2text_lock.locked():
                    audio2text_lock.release()
            else:
                self.DB = sqlite3.connect(audio2text_db_path, check_same_thread=False)
                # '''创建游标'''
                self.cursor = self.DB.cursor()
                self.open_flag = True
                # 创建表
                self.cursor.execute('''CREATE TABLE IF NOT EXISTS Audio2Text (
                               ID INTEGER PRIMARY KEY,
                               msgSvrId INTEGER UNIQUE,
                               Text TEXT NOT NULL
                               );''')
                # 创建索引
                self.cursor.execute('''CREATE INDEX IF NOT EXISTS idx_msg_id ON Audio2Text (msgSvrId);''')
                # 提交更改
                self.DB.commit()

    def get_audio_text(self, reserved0) -> str:
        """
        @param reserved0: 语音id或者消息id
        @return:
        """
        sql = '''
            select text from Audio2Text
            where msgSvrId =?;
        '''
        try:
            audio2text_lock.acquire(True)
            self.cursor.execute(sql, [reserved0])
            result = self.cursor.fetchone()
            if result:
                return result[0]
            else:
                return ""
        except:
            return ""
        finally:
            audio2text_lock.release()

    def add_text(self, msgSvrId, text) -> bool:
        try:
            audio2text_lock.acquire(True)
            sql = '''INSERT INTO Audio2Text (msgSvrId, Text) VALUES (?, ?)'''
            self.cursor.execute(sql, [msgSvrId, text])
            self.DB.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        except:
            return False
        finally:
            audio2text_lock.release()

    def check_msgSvrId_exists(self, msgSvrId) -> bool:
        try:
            audio2text_lock.acquire(True)
            sql = '''SELECT * FROM Audio2Text WHERE msgSvrId = ?'''
            self.cursor.execute(sql, [msgSvrId])
            result = self.cursor.fetchone()
            return result is not None
        except Exception as e:
            logger.error(f"Failed to check msgSvrId in Audio2Text: {e}")
            return False
        finally:
            audio2text_lock.release()

    def close(self):
        if self.open_flag:
            try:
                audio2text_lock.acquire(True)
                self.open_flag = False
                if self.DB:
                    self.DB.close()
            finally:
                audio2text_lock.release()

    def __del__(self):
        self.close()


if __name__ == '__main__':
    db_path = './Msg/MediaMSG.db'
    media_msg_db = MediaMsg()
    audio2text_db = Audio2TextDB()
    reserved = 5434219509914482591
    # path = media_msg_db.get_audio(reserved, r"D:\gou\message\WeChatMsg")
    is_msgSvrId_exists = audio2text_db.check_msgSvrId_exists(reserved)
    print(is_msgSvrId_exists)
    # print(path)
