## wxManager使用教程

## 1、解析数据

```shell
python 1-decrypt.py
```

运行成功之后会生成一个数据库文件夹
* 如果微信版本是4.0的话数据库文件夹是：`./wxid_xxx/db_storage`
* 如果微信版本是3.x的话数据库文件夹是：`./wxid_xxx/Msg`

后面其他操作都会用到这个文件夹

## 2、查看联系人

修改 `2-contact.py` 文件的 `db_dir` 为上面得到的文件夹，如果微信是4.0 `db_version` 设置为4，否则设置为3

```shell
python 2-contact.py
```

## 3、导出数据

```python
import time
from multiprocessing import freeze_support

from exporter.config import FileType
from exporter import HtmlExporter, TxtExporter, AiTxtExporter, DocxExporter, MarkdownExporter, ExcelExporter
from wxManager import DatabaseConnection, MessageType


def export():
    st = time.time()

    db_dir = ''  # 解析后的数据库路径，例如：./db_storage
    db_version = 4  # 数据库版本，4 or 3

    wxid = 'wxid_00112233'  # 要导出好友的wxid
    output_dir = './data/'  # 输出文件夹

    conn = DatabaseConnection(db_dir, db_version)  # 创建数据库连接
    database = conn.get_interface()  # 获取数据库接口

    contact = database.get_contact_by_username(wxid)  # 查找某个联系人
    exporter = HtmlExporter(
        database,
        contact,
        output_dir=output_dir,
        type_=FileType.HTML,
        message_types={MessageType.MergedMessages},  # 要导出的消息类型，默认全导出
        time_range=['2020-01-01 00:00:00', '2035-03-12 00:00:00'],  # 要导出的日期范围，默认全导出
        group_members=None  # 指定导出群聊里某个或者几个群成员的聊天记录
    )

    exporter.start()
    et = time.time()
    print(f'耗时：{et - st:.2f}s')


if __name__ == '__main__':
    freeze_support()
    export()
```