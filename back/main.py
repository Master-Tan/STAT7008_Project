import os
from flask import Flask, jsonify, request, session
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import pandas as pd

import threading
from backendInstance import BackendInstance
from database import select_statement, insert_statement, delete_statement, update_statement

app=Flask(__name__, static_url_path='')
app.config['JWT_SECRET_KEY'] = '123456'  # 更换为你的密钥
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
CORS(app)

# 全局变量
api_key = "sk-6c6a422050da4b4b93767c06f25cc228"

# 多线程
user_threads = dict() # username: key，thread: value
user_backendInstances = dict() # username: key, value: backendInstance

# 后端app相关代码
@app.route('/api/register', methods=['POST'])
def register():
    data= request.get_json()
    print(data)
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    # 创建username命名的文件夹
    folder_path = '../static/' + username
    try:
        os.makedirs(folder_path, exist_ok=True)
    except Exception as e:
        print(f"Error creating folder: {e}")
        return jsonify({"error": "An error occurred during register."}), 500

    if not username:
        return jsonify({'error': 'No Username provided'}), 400
    if not password:
        return jsonify({'error': 'No Password provided'}), 400
    try:
        result = select_statement(table_name='users', \
                        username=username, \
                        select_attributes='*')
        if result:
            return jsonify({"error": "User already exists"}), 400 # user已存在
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        values = [username, hashed_password, email]
        insert_statement('users', values)

        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        # 捕获可能的异常并返回错误信息
        print(f"Error during register: {e}")
        return jsonify({"error": "An error occurred during register."}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username:
        return jsonify({'error': 'No Username provided'}), 400
    if not password:
        return jsonify({'error': 'No Password provided'}), 400

    user = select_statement(table_name='users', \
                            username=username, \
                            select_attributes='*')
    if user and bcrypt.check_password_hash(user['password'], password):
        access_token = create_access_token(identity=username)
        values = [username, '', '', '', '', 'FALSE']
        delete_statement('userBackendInfo', username)
        insert_statement('userBackendInfo', values)
        # 当前初始化user对应的thread
        t_backend = threading.Thread(target=lambda: initializeBackendInstance(username))
        t_backend.start()
        # t_backend = threading.Thread(target=initializeBackendInstance(username))
        # t_backend.start()
        print("break")
        user_threads.update({username: t_backend})
        return jsonify({"access_token": access_token}), 200 # JWT相关
    else:
        return jsonify({"error": "Invalid username or password"}), 401


@app.route('/api/logout', methods=['POST'])
@jwt_required()
def logout():
    print("begin logout")
    # 删除当前用户的数据，如何获取username我没想好
    username = get_jwt_identity() # 获取当前用户的username
    # 删除当前backendInstance
    instance = user_backendInstances[username]
    instance.change_run_flag(False)
    print("half logout!")
    thread = user_threads[username]
    thread.join() # 等待线程结束
    del user_backendInstances[username]
    del user_threads[username]
    try:
        delete_statement(table_name='userBackendInfo', \
                        username=username)
        return jsonify({"message": "Logout successful and user data removed."}), 200
    except Exception as e:
        # 捕获可能的异常并返回错误信息
        print(f"Error during logout: {e}")
        return jsonify({"error": "An error occurred during logout."}), 500


# 清除缓存数据
# @app.route('/api/clear_cache', methods=['POST'])
# @jwt_required()
# def clear_cache():
#     username = get_jwt_identity()
#     values = ['', '', '', '', 'FALSE']
#     update_statement(table_name='userBackendInfo', \
#                      values=values, \
#                      username=username, \
#                      include_columns=['current_answer', 'current_question', 'image_list', 'csv_df', 'upload_flag'])
#     # 删除上一个backendInstance，重新运行一个新的backendInstance
#     instance = user_backendInstances[username]
#     instance.change_run_flag(False)
#     thread = user_threads[username]
#     thread.join() # 等待线程结束
#     del user_backendInstances[username]
#     del user_threads[username]

#     # 当前初始化user对应的thread
#     t_backend = threading.Thread(target=lambda: initializeBackendInstance(username))
#     t_backend.start()
#     user_threads.update({username: t_backend})

#     # 当前username的instance停止，新建一个instance
#     return jsonify({"message": "Cache cleared successfully"}), 200

@app.route('/api/pass_front_question', methods=['POST'])
@jwt_required()
def pass_front_question():
    username = get_jwt_identity()
    data = request.get_json()
    question = data.get('question')
    if not question:
        return jsonify({"error": "Invalid input"}), 400
    
    update_statement(table_name='userBackendInfo', \
                     values=[question], \
                     username=username, \
                     include_columns=['current_question'])

    return jsonify({"message": "Question received and processing."}), 200

@app.route('/api/return_back_answer', methods=['GET'])
@jwt_required()
def return_back_answer():
    username = get_jwt_identity()
    result = select_statement(table_name='userBackendInfo', \
                              username=username, \
                              select_attributes=['current_answer', 'image_list'])
    cur_answer = result['current_answer']
    image_list_str = result['image_list']
    print(image_list_str)
    image_list = image_list_str.split(',')
    print("len(image_list)", len(image_list))
    # 处理image
    image_list = [img for img in image_list if img != ""]
    print("len(image_list)", len(image_list))
    image_list = ['static/'+username+'/'+img for img in image_list]

    print("cur_answer: ", cur_answer)
    if len(cur_answer) == 0 and len(image_list) == 0: # 同时没有文字回复和图像回复
        return jsonify({"error": "No answer available."}), 400
    
    update_statement(table_name='userBackendInfo', \
                     values=['', ''], \
                     username=username, \
                     include_columns=['current_answer', 'image_list'])
    print(jsonify({"answer": cur_answer, "image_paths": image_list}))
    return jsonify({"answer": cur_answer, "image_paths": image_list}), 200 
    # 前端处理返回数据，可能只有一种数据

@app.route('/api/upload_csv', methods=['POST'])
@jwt_required()
def upload_csv():
    username = get_jwt_identity()
    file = request.files['file']
    if file is None:
        return jsonify({"error": "File upload failed."}), 400
    
    csv = pd.read_csv(file)  # 将CSV数据加载到缓存中
    # 保存为 Excel 文件
    csv_df = '../static/' + username + '/my_excel.csv'  # 指定输出的 Excel 文件名
    csv.to_csv(csv_df, index=False)  # index=False 表示不保存行索引

    update_statement(table_name='userBackendInfo', \
                     values=[csv_df, 'TRUE'], \
                     username=username, \
                     include_columns=['csv_df', 'upload_flag'])
    
    return jsonify({"message": "File uploaded successfully"}), 200

def initializeBackendInstance(username):
    global api_key
    instance = BackendInstance(username=username, api_key=api_key, verbose=True)
    user_backendInstances.update({username: instance})
    instance.run()
    
    

def main():
    app.run(host="127.0.0.1", port="5000", debug=False)


if __name__ == '__main__':
    main()