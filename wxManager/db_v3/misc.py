import hashlib
import io
import os.path
import shutil
import sqlite3
import time
import traceback

from PIL import Image

from wxManager.merge import increase_update_data
from wxManager.log import logger
from wxManager.model import DataBaseBase


class Misc(DataBaseBase):

    def get_avatar_buffer(self, username):
        if not self.open_flag:
            return None
        sql = '''
            select smallHeadBuf
            from ContactHeadImg1
            where usrName=?;
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql, [username])
        result = cursor.fetchall()
        cursor.close()
        self.DB.commit()
        if result:
            return result[0][0]
        else:
            return b''

    def set_avatar_buffer(self, username, img_path):
        try:
            # 打开图片并缩放
            with Image.open(img_path) as img:
                img = img.resize((128, 128))

                # 将图片转换为二进制格式
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')  # 可以根据需要更改格式
                img_binary = img_byte_arr.getvalue()
                md5_hash = hashlib.md5()
                md5_hash.update(img_binary)

            update_sql = '''
                UPDATE ContactHeadImg1
                SET createTime = ?,smallHeadBuf=?
                WHERE usrName = ?
            '''
            cursor = self.DB.cursor()
            cursor.execute(update_sql, [int(time.time()), img_binary, username, md5_hash.hexdigest()])
            # 检查是否有行被更新
            if cursor.rowcount == 0:
                # 如果没有更新，则插入新记录
                insert_sql = '''
                                    INSERT INTO head_image (username,md5, image_buffer,update_time)
                                    VALUES (?, ?,?,?)
                                '''
                cursor.execute(insert_sql, [username, md5_hash.hexdigest(), int(time.time()), img_binary])
            cursor.close()
            self.commit()  # 提交更改
        except:
            logger.error(traceback.format_exc())
            return False
        return True

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_update_data(db_path, self.DB.cursor(), self.DB, 'ContactHeadImg1', 'usrName', 0)
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()
