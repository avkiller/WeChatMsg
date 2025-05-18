import os
import sqlite3
import traceback

from wxManager.log import logger


def table_exists(conn, table_name):
    """检查表是否存在"""
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone()[0] > 0


def get_create_statements(conn, table_name, object_type):
    """获取指定表的 CREATE TABLE 或 CREATE INDEX 语句"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='{object_type}' AND tbl_name=?", (table_name,))
    return [row[0] for row in cursor.fetchall() if row[0]]  # 过滤掉 None 值


def increase_data(db_path, src_cursor, src_conn, table_name, col_name, col_index=-1, exclude_column=''):
    """
    将db_path数据库的内容增量写入connect数据库中
    @param db_path: 新的数据库路径
    @param src_cursor: 待写入数据库游标
    @param src_conn: 待写入数据库连接
    @param table_name: 待写入的表名
    @param col_name: 根据该列进行判断是否是新增数据
    @param col_index: 待写入的列号
    @param exclude_column: 是否不考虑某一列（针对某一列是自增ID的表）
    @return:
    """
    if not (os.path.exists(db_path) or os.path.isfile(db_path)):
        print(f'{db_path} 不存在')
        return
    if not src_cursor or not src_conn:
        print(f'{db_path} 数据库连接无效，增量解析失败')
        return
    tgt_conn = sqlite3.connect(db_path)
    tgt_cur = tgt_conn.cursor()

    try:
        if not table_exists(src_conn, table_name):
            # 复制表结构
            create_table_sql = get_create_statements(tgt_conn, table_name, "table")
            if create_table_sql:
                src_conn.execute(create_table_sql[0])  # 执行 CREATE TABLE 语句
                print(f"表 {table_name} 结构已复制")

            # 复制索引
            create_index_sql_list = get_create_statements(tgt_conn, table_name, "index")
            for create_index_sql in create_index_sql_list:
                src_conn.execute(create_index_sql)  # 执行 CREATE INDEX 语句
                print(f"索引已复制: {create_index_sql}")
        # 获取列名
        src_cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = src_cursor.fetchall()
        column_names = [info[1] for info in columns_info]
        if columns_info and exclude_column:
            try:
                exclude_col_index = column_names.index(exclude_column)
            except ValueError:
                print(f"错误: 列 {exclude_column} 在表 {table_name} 中不存在")
                return
            column_names = column_names[:exclude_col_index]+column_names[exclude_col_index+1:]
        num_columns = len(column_names)
        if col_index == -1:
            try:
                col_index = column_names.index(col_name)
            except ValueError:
                print(f"错误: 列 {col_name} 在表 {table_name} 中不存在")
                return
        # 从数据库B中选择主键不在数据库A中的行
        query = f"""
           SELECT {', '.join(column_names)}
           FROM {table_name} 
        """
        tgt_cur.execute(query)
        target_rows = tgt_cur.fetchall()
        query = f'''
        SELECT {col_name}
        FROM {table_name}
        '''
        src_cursor.execute(query)
        source_rows = src_cursor.fetchall()

        source_rows = {r[0] for r in source_rows}
        rows_to_insert = [row for row in target_rows if row[col_index] not in source_rows]
        if rows_to_insert:
            insert_query = f"""
                INSERT INTO {table_name} ({', '.join(column_names)})
                VALUES ({', '.join(['?'] * num_columns)})
            """
            src_cursor.executemany(insert_query, rows_to_insert)
            src_conn.commit()
            print(f"{len(rows_to_insert)} 行已插入到 {table_name} 表中")
        else:
            pass
            # print(f"没有需要插入的数据，{table_name} 表已是最新")
    except sqlite3.Error as e:
        print(f"{db_path} 数据库操作错误: {e}")
    finally:
        tgt_cur.close()
        tgt_conn.close()


def increase_update_data(db_path, src_cur, src_conn, table_name, col_name, col_index=-1, exclude_first_column=False):
    """
    将 db_path 数据库的内容增量写入 src_conn 连接的数据库，如果有冲突则删除旧数据并更新
    :param db_path: 目标数据库文件路径
    :param src_cur: 源数据库游标
    :param src_conn: 源数据库连接
    :param table_name: 需要同步的表名
    :param col_name: 用于匹配的列名
    :param col_index: 指定列的索引（默认为 -1，即自动检测）
    :param exclude_first_column: 是否排除第一列
    """
    if not (os.path.exists(db_path) or os.path.isfile(db_path)):
        print(f'{db_path} 不存在')
        return

    tgt_conn = sqlite3.connect(db_path)
    tgt_cur = tgt_conn.cursor()
    try:
        if not table_exists(tgt_conn, table_name):
            # 复制表结构
            create_table_sql = get_create_statements(src_conn, table_name, "table")
            if create_table_sql:
                tgt_conn.execute(create_table_sql[0])  # 执行 CREATE TABLE 语句
                print(f"表 {table_name} 结构已复制")

            # 复制索引
            create_index_sql_list = get_create_statements(src_conn, table_name, "index")
            for create_index_sql in create_index_sql_list:
                tgt_conn.execute(create_index_sql)  # 执行 CREATE INDEX 语句
                print(f"索引已复制: {create_index_sql}")

        # 获取列名
        src_cur.execute(f"PRAGMA table_info({table_name})")
        columns_info = src_cur.fetchall()
        if exclude_first_column:
            columns_info = columns_info[1:]

        column_names = [info[1] for info in columns_info]
        num_columns = len(column_names)

        if col_index == -1:
            try:
                col_index = column_names.index(col_name)
            except ValueError:
                print(f"错误: 列 {col_name} 在 {table_name} 表中不存在。")
                return

        # 查询目标数据库的数据
        query = f"SELECT {', '.join(column_names)} FROM {table_name}"
        tgt_cur.execute(query)
        source_rows = set(tgt_cur.fetchall())  # 使用 set() 加速查询

        # 查询源数据库已有的数据
        src_cur.execute(query)
        existing_rows = set(src_cur.fetchall())

        # 需要删除并重新插入的行
        rows_to_insert = [row for row in source_rows if row not in existing_rows]

        if rows_to_insert:
            delete_query = f"DELETE FROM {table_name} WHERE {col_name} = ?"
            src_cur.executemany(delete_query, [(row[col_index],) for row in rows_to_insert])
            src_conn.commit()

            insert_query = f"INSERT INTO {table_name} ({', '.join(column_names)}) VALUES ({', '.join(['?'] * num_columns)})"
            src_cur.executemany(insert_query, rows_to_insert)
            src_conn.commit()
            print(f"{len(rows_to_insert)} 行已更新到 {table_name} 表中。")
        else:
            pass
            # print(f"没有需要插入的数据，{table_name} 表已是最新。")
    except sqlite3.Error as e:
        print(f"{db_path} 数据库操作错误: {e}")
    finally:
        tgt_cur.close()
        tgt_conn.close()


if __name__ == "__main__":
    # 源数据库文件列表
    source_databases = ["Msg0/MSG2.db", "Msg/MSG2.db", "Msg/MSG3.db"]
