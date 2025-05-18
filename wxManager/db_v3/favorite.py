import os.path
import sqlite3
import threading
from datetime import date
from typing import Tuple

from wxManager.db_v3.msg import convert_to_timestamp

lock = threading.Lock()
DB = None
cursor = None
db_path = '.'


class Favorite:

    def get_items(self, time_range: Tuple[int | float | str | date, int | float | str | date] = None, ):
        if time_range:
            start_time, end_time = convert_to_timestamp(time_range)
        sql = f'''
            select FavLocalID, Type, FromUser, RealChatName, SearchKey, UpdateTime, XmlBuf
            from FavItems
            where StrTalker=?
            {'AND UpdateTime>' + str(start_time) + ' AND UpdateTime<' + str(end_time) if time_range else ''}
            order by UpdateTime
        '''
        res = []
        try:
            lock.acquire(True)
            self.cursor.execute(sql)
            res = self.cursor.fechall()
            self.DB.commit()
        except:
            res = []
        finally:
            lock.release()
        return res if res else []
