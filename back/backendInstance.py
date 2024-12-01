import os
from langchain_core.messages import *
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing_extensions import TypedDict,Annotated, Union
from database import select_statement, update_statement

class BackendInstance:
    def __init__(self, api_key, username, verbose=False):
        from graph_construct import build_graph
        self.api_key = api_key
        self.graph = build_graph()
        self.verbose = verbose
        self.username = username
        self.run_flag = True

    def run(self):
        from graph_construct import init_state
        # draw_graph(self.graph)
        result = select_statement(table_name='userBackendInfo', \
                                username=self.username, \
                                select_attributes=['csv_df', 'upload_flag'])
        df_path = result['csv_df']
        state0 = init_state(api_key=self.api_key, df_path=df_path, verbose=self.verbose)
        self.run_graph(state0, self.graph, debug=False)
    
    def change_run_flag(self, flag):
        self.run_flag = flag
        return
    
    def run_graph(self, init_state, graph, debug=True):
        should_init = True
        while True:
            if self.run_flag is False:
                break
            # 获取当前问题
            user_input = ""
            while len(user_input) == 0:
                if self.run_flag is False:
                    break
                result = select_statement(table_name='userBackendInfo', \
                                username=self.username, \
                                select_attributes=['current_question'])
                user_input = result['current_question']
            if self.run_flag is False:
                break
            print("user input: ", user_input)
            result = select_statement(table_name='userBackendInfo', \
                                username=self.username, \
                                select_attributes=['csv_df', 'upload_flag'])
            upload_flag = result['upload_flag']
            df_path = result['csv_df']
            print("upload_flag = ", upload_flag, "df_path = ", df_path)
            # TODO: 不确定BOOLEAN输出是否是什么？
            if user_input.lower() in ["quit","exit","q","bye"]:
                print("Goodbye!")
                break
            config = {"configurable": {"thread_id": "123"}}

            if should_init:
                state = init_state
                should_init = False
            if upload_flag == 'TRUE':
                # 已上传文件
                state["df_path"] = df_path
                # only changes when new csv uploaded
                df_dir = os.path.dirname(df_path)

                state["messages"] = [("user", user_input)]

                orig_files = set(os.listdir(df_dir))
                # Invoke whole llm graph
                events = graph.stream(state,
                                        config,
                                        stream_mode="values")

                for event in events:
                    message = event["messages"][-1]
                    if type(message) != HumanMessage:
                        if debug: # 是否打印所有过程步骤
                            message.pretty_print()
                # use message in the last loop
                print("Assistant: ", message.content)
                self.upload_ai_chat(message.content)

                # 清空当前的问题
                update_statement(table_name='userBackendInfo', \
                                values=[''], \
                                username=self.username, \
                                include_columns=['current_question'])
                final_files = set(os.listdir(df_dir))
                new_files = list(final_files - orig_files)
                self.upload_ai_image(new_files)
            else:
                print("Assistant: ", "Hello, please upload your file first!")
                self.upload_ai_chat("Hello, please upload your file first!")
                # 清空当前的问题
                update_statement(table_name='userBackendInfo', \
                                values=[''], \
                                username=self.username, \
                                include_columns=['current_question'])
        print(self.username, " exit")

    def upload_ai_chat(self, chat:str):
        """
        将AI的回答保存在后端全局变量cur_answer中
        :param chat: AI回答的文字内容
        :return: None
        """
        print("--> upload_ai_chat")
        # 将大模型的输出chat，保存在数据库中
        chat
        update_statement(table_name='userBackendInfo', \
                        values=[chat], \
                        username=self.username, \
                        include_columns=['current_answer'])

    def upload_ai_image(self, path_list:list[str]):
        """
        将获取到的图片保存在后端本地
        :param path_list: 在回答期间新增的图像文件路径
                        path_list = [] 本次回答没有新增图片
                        path_list = ['img_path1', 'img_path2'] 本次回答新增了多张图片
        :return: None
        """
        print("--> upload_ai_image")
        # 在这里添加把图片发送回前端的代码
        # 假设您有一个字符串列表
        # 使用 join() 方法将列表转换为以逗号分隔的字符串
        path_list_str = ','.join(path_list)

        update_statement(table_name='userBackendInfo', \
                        values=[path_list_str], \
                        username=self.username, \
                        include_columns=['image_list'])


def receive_user_excel():
    """
    用户应该在这里向后端发送excel文件
    如果用户点击了上传按钮，则upload_flag==True，用户上传的csv文件路径在此处以固定字符串 df_path 代替
    实际返回的df_path应为上传的excel在系统中保存的路径。（注意要带上.csv或.excel路径）
    如果用户没有点击上传按钮，则直接返回None

    同时，在用户第一次进入界面，发送第一条问题的时候会强制调用此函数一次，保证后台一定有可用的数据表
    （首次发送消息时若没有上传数据表，请将发送按钮设置为灰色不可用）
    对于每一个用户，他们的数据（excel和ai生成的图片）都应保存在以他们用户名命名的临时文件夹里

    :return: df_path(str of path, or None)
    """
    print("--> receive_user_excel")
    global csv_df, upload_flag
    # upload_flag = True # 修改这里，根据用户是否点击上传按钮确定是True/False ->若是True，请获取df_path（上传csv的文件路径）
    if upload_flag == True:
        # TODO: 直接获取dataframe，不是path
        # 测试阶段暂时不改，直接使用原始的csv
        return './user_1/my_excel.csv'
        return csv_df 
    return None

