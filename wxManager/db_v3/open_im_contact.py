import os.path
import shutil
import sqlite3
import threading
import traceback

from wxManager.merge import increase_update_data
from wxManager.log import logger
from wxManager.model import DataBaseBase


class OpenIMContactDB(DataBaseBase):
    def get_contacts(self):
        result = []
        if not self.open_flag:
            return result
        try:
            sql = '''SELECT UserName,NickName,Type,Remark,BigHeadImgUrl,SmallHeadImgUrl,Source,NickNamePYInit,NickNameQuanPin,RemarkPYInit,RemarkQuanPin,CustomInfoDetail,DescWordingId
                    FROM OpenIMContact
                    WHERE Type!=0 AND Type!=4
                  '''
            cursor = self.DB.cursor()
            cursor.execute(sql)
            result = cursor.fetchall()
            self.commit()  # 提交更改
        except sqlite3.OperationalError:
            logger.error(f'数据库错误:\n{traceback.format_exc()}')
        res = []
        if result:
            for contact in result:
                wording = self.get_wordinfo(contact[12])
                if wording:
                    res.append((*contact, wording[1]))
                else:
                    res.append((*contact, ''))
        return res

    def set_remark(self, username, remark):
        update_sql = '''
            UPDATE OpenIMContact
            SET Remark = ?
            WHERE UserName = ?
        '''
        cursor = self.DB.cursor()
        cursor.execute(update_sql, [remark, username])
        self.commit()  # 提交更改
        return True

    def get_contact_by_username(self, username_):
        result = []
        if not self.open_flag:
            return result
        try:
            sql = '''SELECT UserName,NickName,Type,Remark,BigHeadImgUrl,SmallHeadImgUrl,Source,NickNamePYInit,NickNameQuanPin,RemarkPYInit,RemarkQuanPin,CustomInfoDetail,DescWordingId
                    FROM OpenIMContact
                    WHERE UserName=?
                  '''
            cursor = self.DB.cursor()
            cursor.execute(sql, [username_])
            result = cursor.fetchone()
            self.commit()  # 提交更改
        except sqlite3.OperationalError:
            logger.error(f'数据库错误:\n{traceback.format_exc()}')
        if result:
            result = list(result)
            wording = self.get_wordinfo(result[12])
            if wording:
                result.append(wording[1])
            else:
                result.append('')
        return result

    def get_wordinfo(self, wording_id):
        """
        获取企业微信所在的公司
        @param wording_id:
        @return: WordingId, id
                Wording, 企业名
                Pinyin, 拼音
                Quanpin, 全拼
                UpdateTime 更新时间
        """
        result = []
        return result
        if not self.open_flag:
            return result
        try:
            sql = '''SELECT WordingId,Wording,Pinyin,Quanpin,UpdateTime
                FROM OpenIMWordingInfo
                WHERE WordingId=?
            '''
            cursor = self.DB.cursor()
            cursor.execute(sql, [wording_id])
            result = cursor.fetchone()
            self.commit()  # 提交更改
        except sqlite3.OperationalError:
            logger.error(f'数据库错误:\n{traceback.format_exc()}')
        return result


    def increase_source(self, db_path_):
        if not (os.path.exists(db_path_) or os.path.isfile(db_path_)):
            print(f'{db_path_} 不存在')
            return
        if not self.sourceDB or not self.sourceCursor:
            print(f'企业微信数据异常，尝试修复···')
            try:
                os.remove(open_im_source_db_path)
            except:
                pass
            try:
                shutil.copy(db_path_, open_im_source_db_path)
            except:
                pass
            return
        try:
            lock.acquire(True)
            # 获取列名
            increase_update_data(db_path_, self.sourceCursor, self.sourceDB, 'OpenIMWordingInfo', 'WordingId', 2)
        except sqlite3.Error as e:
            print(f"数据库操作错误: {e}")
            self.sourceDB.rollback()
        finally:
            lock.release()

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_update_data(db_path, self.cursor, self.DB, 'OpenIMContact', 'UserName', 0)
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()


if __name__ == '__main__':
    db_path = "./Msg/OpenIMContact.db"
    msg = OpenIMContactDB()
    msg.init_database()
    contacts = msg.get_contacts()
    for contact in contacts:
        print(contact)
