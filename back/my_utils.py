import os
from langchain_core.messages import *
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing_extensions import TypedDict,Annotated, Union



def print_var(variable):
    import inspect
    stack = inspect.stack()
    frame = stack[1][0]
    locals_dict = frame.f_locals

    for name, value in locals_dict.items():
        if value is variable:
            print(f"{name.center(20, '#')}: {value}")
            return name
    return print(f"{'Var'.center(20, '#')}: {variable}")

def print_messages(messages):
    messages = [messages] if type(messages) != list else messages
    print("".center(100,"#"))
    for m in messages:
        m.pretty_print()
    print("".center(100, "#" ))

def set_prompt(messages:Union[AnyMessage,list],prompt:str):
    """
    给输入agent的消息前添加专属该agent的prompt
    :param messages: 原先的历史消息记录，或单条消息也可
    :param prompt: 要添加的prompt
    :return:
    """
    messages = [messages] if type(messages)!=list else messages
    messages.insert(-1,SystemMessage(prompt))
    return messages

def get_llm(model,api_key=None,base_url="Alibaba"):
    if api_key is None:
        llm = ChatOllama(model=model, temperature=0)
    else:
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1" if base_url=="Alibaba" else base_url
        llm = ChatOpenAI(model=model,
                         base_url=base_url,
                         temperature=0,
                         api_key=api_key)
    return llm

def called_tool(message,tool_name):
    """
    返回某条消息是否调用了某个函数
    :param message: 传入的最后一条消息
    :param tool_name: 执行的tool名字
    :return:
    """
    if type(message)==ToolMessage:
        if message.name == tool_name:
            return True
    return False

def run_graph(init_state,graph,debug=True):
    # from frontend_connect import receive_user_chat, receive_user_excel, upload_ai_chat, upload_ai_image
    from main import receive_user_chat, receive_user_excel, upload_ai_chat, upload_ai_image
    should_init = True
    while True:
        user_input = receive_user_chat()
        # TODO
        while user_input is None:
            user_input = receive_user_chat()
            # print("user input: ", user_input)
        print("user input: ", user_input)
        df_path = receive_user_excel()
        if user_input.lower() in ["quit","exit","q","bye"]:
            print("Goodbye!")
            break
        config = {"configurable": {"thread_id": "123"}}

        if should_init:
            state = init_state
            should_init = False
        if df_path != None:
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
        print("Assistant: ",message.content)
        upload_ai_chat(message.content)
        final_files = set(os.listdir(df_dir))
        new_files = list(final_files - orig_files)
        upload_ai_image(new_files)

def draw_graph(graph):
    from matplotlib import pyplot as plt
    import numpy as np
    from io import BytesIO
    from PIL import Image as PILImage
    from IPython.display import Image, display
    img = Image(graph.get_graph().draw_mermaid_png())
    img_bytes = BytesIO(img.data)  # img_obj.data 包含图片的原始字节数据
    pil_image = PILImage.open(img_bytes)
    img_array = np.array(pil_image)

    # 使用 matplotlib 显示图片
    plt.imshow(img_array)
    plt.axis('off')  # 关闭坐标轴显示
    # plt.show()

def trim_messages(messages,llm):
    """
    recieves previous messages from state.
    return corresponding trimmed & summarized messages
    """

    n_trim = {"from": 10, "to": 3}
    messages = [m for m in messages if type(m) != ToolMessage]

    if len(messages) >= n_trim["from"]:
        new_messages = messages[-n_trim["to"]:]
        old_messages = messages[:-n_trim["to"]]
        response = llm.invoke(old_messages)
        new_messages.insert(0, HumanMessage(response.content))
        print("new_messages",new_messages)
        return new_messages

    return messages

