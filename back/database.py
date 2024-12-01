import pymysql

# Database connection
def get_db_connection():
    connection = pymysql.connect(
        host='127.0.0.1',
        port=3306, 
        user='root',       # MySQL 用户名
        password='1887415157qwerty',   # MySQL 密码
        db='stat7008_project',            # 数据库名称
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    return connection

def select_statement(table_name, username, select_attributes):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        # 检查用户名是否已存在
        sql = f"SELECT {', '.join(select_attributes)} FROM {table_name} WHERE username = %s"
        # 执行查询
        cursor.execute(sql, (username,))
        result = cursor.fetchone()  # 如果只期望一个结果
        # print("select result: ", result)
    connection.close()
    # print("select ok!")
    return result


def insert_statement(table_name, values):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        # 查询表的列名
        print("insert begin")
        if table_name == 'users':
            attributes = ['username', 'password', 'email']
        else:
            cursor.execute(f"SELECT column_name FROM information_schema.columns \
                WHERE table_name = '{table_name}'")
            columns = cursor.fetchall()
            attributes = [column['COLUMN_NAME'] for column in columns]
        print("attributes = ", attributes)

        placeholders = ', '.join(['%s'] * len(values))  # 创建占位符
        columns = ', '.join(attributes)  # 将属性列表转换为逗号分隔的字符串
        sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"  # 替换为实际表名
        print("sql = ", sql)
        # 执行插入操作
        cursor.execute(sql, values)
        connection.commit()  # 提交更改
    connection.close()  # 关闭连接

def delete_statement(table_name, username):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        sql = f"DELETE FROM {table_name} WHERE username = %s"  # 替换为实际表名
        print("sql = ", sql)
        cursor.execute(sql, (username,))
        connection.commit()
    connection.close()
    print("delete ok!")


def update_statement(table_name, values, username, include_columns):
    connection = get_db_connection()
    with connection.cursor() as cursor:
        # 验证 include_columns 是否与 values 的长度匹配
        if len(values) != len(include_columns):
            raise ValueError("The number of values must match the number of columns to update.")
        # 构建 SET 子句
        set_clause = ', '.join([f"{include_columns[i]} = %s" for i in range(len(values))])  # 使用占位符
        
        # 构建 SQL 语句
        sql = f"UPDATE {table_name} SET {set_clause} WHERE username = %s"

        # 执行更新操作
        cursor.execute(sql, list(values) + [username])  # 将 username 作为参数传入
        connection.commit()  # 提交更改
    connection.close()  # 关闭连接