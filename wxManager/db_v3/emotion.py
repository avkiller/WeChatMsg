import os.path
import sqlite3
import threading
import traceback

from wxManager.merge import increase_data
from wxManager.model import DataBaseBase

lock = threading.Lock()
# db_path = "./app/Database/Msg/Emotion.db"
db_path = '.'


def singleton(cls):
    _instance = {}

    def inner():
        if cls not in _instance:
            _instance[cls] = cls()
        return _instance[cls]

    return inner


# 一定要保证只有一个实例对象

class Emotion(DataBaseBase):

    def get_emoji_url(self, md5: str, thumb: bool) -> str | bytes:
        """供下载用，返回可能是url可能是bytes"""
        if thumb:
            sql = """
                select
                    case
                        when thumburl is NULL or thumburl = '' then cdnurl
                        else thumburl
                    end as selected_url
                from CustomEmotion
                where md5 = ?
            """
        else:
            sql = """
                select CDNUrl
                from CustomEmotion
                where md5 = ?
            """
        cursor = self.DB.cursor()
        try:
            cursor.execute(sql, [md5])
            return cursor.fetchone()[0]
        except:
            md5 = md5.upper()
            sql = f"""
                select {"Thumb" if thumb else "Data"}
                from EmotionItem
                where md5 = ?
            """
            cursor.execute(sql, [md5])
            res = cursor.fetchone()
            return res[0] if res else ""
        finally:
            lock.release()

    def get_emoji_URL(self, md5: str, thumb: bool):
        """只管url，另外的不管"""
        if thumb:
            sql = """
                select
                    case
                        when thumburl is NULL or thumburl = '' then cdnurl
                        else thumburl
                    end as selected_url
                from CustomEmotion
                where md5 = ?
            """
        else:
            sql = """
                select CDNUrl
                from CustomEmotion
                where md5 = ?
            """
        cursor = self.DB.cursor()
        try:
            cursor.execute(sql, [md5])
            return cursor.fetchone()[0]
        except:
            return ""

    def get_emoji_desc(self, md5: str):
        sql = '''
        select Des
        from EmotionDes1
        where MD5=? or MD5=?
        '''
        cursor = self.DB.cursor()
        try:
            cursor.execute(sql, [md5, md5.upper()])
            result = cursor.fetchone()
            if result:
                return result[0][6:].decode('utf-8')
            return ""
        except:
            return ""

    def get_emoji_data(self, md5: str, thumb=False):
        sql = f'''
                select {'Thumb' if thumb else 'Data'}
                from EmotionItem
                where MD5=? or MD5=?
                '''
        cursor = self.DB.cursor()
        try:
            cursor.execute(sql, [md5, md5.upper()])
            result = cursor.fetchone()
            if result:
                return result[0]
            return b""
        except:
            return b""

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            cursor = self.DB.cursor()
            # 获取列名
            increase_data(db_path, cursor, self.DB, 'CustomEmotion', 'MD5', 0)
            increase_data(db_path, cursor, self.DB, 'EmotionDes1', 'MD5', 1, 'localId')
            increase_data(db_path, cursor, self.DB, 'EmotionItem', 'MD5', 1, 'localId')
            increase_data(db_path, cursor, self.DB, 'EmotionPackageItem', 'ProductId', 0, 'localId')
            increase_data(db_path, cursor, self.DB, 'EmotionOrderInfo', 'MD5', 0, 'localId')
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()
