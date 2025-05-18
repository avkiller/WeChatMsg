import os.path
import shutil
import sqlite3
import threading
import traceback

from wxManager.merge import increase_update_data
from wxManager.log import logger
from wxManager.model import DataBaseBase
from wxManager.model.contact import Contact

lock = threading.Lock()
# db_path = "./app/Database/Msg/MicroMsg.db"
db_path = '.'


def singleton(cls):
    _instance = {}

    def inner():
        if cls not in _instance:
            _instance[cls] = cls()
        return _instance[cls]

    return inner


def is_database_exist():
    return os.path.exists(db_path)


class MicroMsg(DataBaseBase):

    def get_label_by_id(self, label_id) -> str:
        sql = '''
            select LabelName from ContactLabel
            where LabelId = ?
        '''
        try:
            cursor = self.DB.cursor()
            cursor.execute(sql, [label_id])
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                return ''
        except:
            return ''

    def get_labels(self, label_id_list) -> str:
        if not label_id_list:
            return ''
        return ','.join(map(self.get_label_by_id, label_id_list.strip(',').split(',')))

    def get_contact(self) -> list:
        if not self.open_flag:
            return []
        try:
            sql = '''SELECT UserName, Alias, Type, Remark, NickName, PYInitial, RemarkPYInitial, ContactHeadImgUrl.smallHeadImgUrl, ContactHeadImgUrl.bigHeadImgUrl,ExTraBuf,LabelIDList
                    FROM Contact
                    INNER JOIN ContactHeadImgUrl ON Contact.UserName = ContactHeadImgUrl.usrName
                    WHERE (Type!=4 AND Type!=0)
                    ORDER BY 
                        CASE
                            WHEN RemarkQuanPin = '' THEN QuanPin
                            ELSE RemarkQuanPin
                        END ASC
                  '''
            cursor = self.DB.cursor()
            cursor.execute(sql)
            result = cursor.fetchall()
        except sqlite3.OperationalError:
            # lock.acquire(True)
            sql = '''SELECT UserName, Alias, Type, Remark, NickName, PYInitial, RemarkPYInitial, 
            ContactHeadImgUrl.smallHeadImgUrl, ContactHeadImgUrl.bigHeadImgUrl,ExTraBuf,"None" 
            FROM Contact INNER 
            JOIN ContactHeadImgUrl ON Contact.UserName = ContactHeadImgUrl.usrName WHERE (Type!=4 AND Type!=0) 
            AND NickName != '' ORDER BY CASE WHEN RemarkQuanPin = '' THEN QuanPin ELSE RemarkQuanPin END ASC'''
            self.cursor.execute(sql)
            result = self.cursor.fetchall()
        return result

    def get_contact_by_username(self, username) -> list:
        if not self.open_flag:
            return []
        try:
            sql = '''
                   SELECT UserName, Alias, Type, Remark, NickName, PYInitial, RemarkPYInitial, ContactHeadImgUrl.smallHeadImgUrl, ContactHeadImgUrl.bigHeadImgUrl,ExTraBuf,LabelIDList
                   FROM Contact
                   INNER JOIN ContactHeadImgUrl ON Contact.UserName = ContactHeadImgUrl.usrName
                   WHERE UserName = ?
                '''
            cursor = self.DB.cursor()
            cursor.execute(sql, [username])
            result1 = cursor.fetchone()
        except sqlite3.OperationalError:
            # 解决ContactLabel表不存在的问题
            # lock.acquire(True)
            sql = '''
               SELECT UserName, Alias, Type, Remark, NickName, PYInitial, RemarkPYInitial, ContactHeadImgUrl.smallHeadImgUrl, ContactHeadImgUrl.bigHeadImgUrl,ExTraBuf,""
               FROM Contact
               INNER JOIN ContactHeadImgUrl ON Contact.UserName = ContactHeadImgUrl.usrName
               WHERE UserName = ?
            '''
            self.cursor.execute(sql, [username])
            result1 = self.cursor.fetchone()
        if result1:
            result = [*result1[:-1], self.get_labels(result1[-1])]
            return result
        else:
            return []

    def set_remark(self, username, remark) -> bool:
        try:
            update_sql = '''
                UPDATE Contact
                SET Remark = ?
                WHERE UserName = ?
            '''
            cursor = self.DB.cursor()
            cursor.execute(update_sql, [remark, username])
            self.commit()  # 提交更改
        except:
            return False
        return True

    def set_head_image(self, username, image_url):
        pass

    def get_chatroom_info(self, chatroomname):
        """
        获取群聊信息
        """
        if not self.open_flag:
            return None
        sql = '''SELECT ChatRoomName, RoomData,UserNameList,DisplayNameList FROM ChatRoom WHERE ChatRoomName = ?'''
        cursor = self.DB.cursor()
        cursor.execute(sql, [chatroomname])
        result = cursor.fetchone()
        return result

    def add_contact(self, contact: Contact):
        sql1 = '''
        insert into Contact (UserName,Alias,Remark,NickName,Type)
        values(?,?,?,?,10086);
        '''
        sql2 = '''
        insert into ContactHeadImgUrl (usrName,smallHeadImgUrl,bigHeadImgUrl)
        values(?,?,?);
        '''
        try:
            cursor = self.DB.cursor()
            cursor.execute(sql1, [contact.wxid, contact.alias, contact.remark, contact.nickname])
            cursor.execute(sql2, [contact.wxid, contact.small_head_img_url, contact.big_head_img_url])
            self.commit()
        except:
            logger.error(traceback.format_exc())
        return True

    def get_session(self):
        """
        获取聊天对话
        @return:
        """
        if not self.open_flag:
            return None
        sql = '''
        SELECT strUsrName, nOrder,nUnreadCount,strNickName ,nIsSend,strContent,nMsgType,nTime,strftime('%Y/%m/%d', nTime, 'unixepoch','localtime') AS strTime
        FROM Session
        '''
        cursor = self.DB.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        if result:
            result.reverse()
        return result

    def merge(self, db_path):
        if not (os.path.exists(db_path) or os.path.isfile(db_path)):
            print(f'{db_path} 不存在')
            return
        try:
            # 获取列名
            increase_update_data(db_path, self.cursor, self.DB, 'ChatRoom', 'ChatRoomName', 0)
            increase_update_data(db_path, self.cursor, self.DB, 'ChatRoomInfo', 'ChatRoomName', 0)
            increase_update_data(db_path, self.cursor, self.DB, 'Contact', 'UserName', 0)
            increase_update_data(db_path, self.cursor, self.DB, 'ContactHeadImgUrl', 'usrName', 0)
            increase_update_data(db_path, self.cursor, self.DB, 'ContactLabel', 'LabelId', 0)
            increase_update_data(db_path, self.cursor, self.DB, 'Session', 'strUsrName', 0)
        except:
            print(f"数据库操作错误: {traceback.format_exc()}")
            self.DB.rollback()


if __name__ == '__main__':
    db_path = "./Msg/MicroMsg.db"
    msg = MicroMsg()
    msg.init_database()
    contacts = msg.get_contact()

    sessions = msg.get_session()
    print(sessions)
    for session in sessions:
        print(session)
