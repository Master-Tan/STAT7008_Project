import os.path

import pandas as pd
from langchain_core.messages import RemoveMessage
from typing_extensions import Annotated,TypedDict
from langchain_core.tools import tool
from langchain_community.retrievers import TavilySearchAPIRetriever
from langchain_experimental.agents import create_pandas_dataframe_agent
from langgraph.prebuilt import *
from langchain_core.messages import *
from langgraph.graph import *
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
import json
from my_utils import *


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages] # 这样的定义方式等于：langgraph.graph.MessagesState
    df_path: str
    api_key: str
    model: str
    verbose: bool
    # temp_df: pd.DataFrame

def init_state(api_key,df_path, verbose=False):
    state = State()
    state["api_key"] = api_key
    state["df_path"] = df_path
    state["model"] = "qwen-turbo"
    state["verbose"] = verbose
    init_message = SystemMessage("You are a professional data analyst, who is good at using pandas to analyze given dataset.")
    state["messages"] = [init_message]
    return state

# @tool
# def plotChart(data: str) -> int:
#     """Plots json data using plotly Figure. Use it only for ploting charts and graphs."""
#     # Load JSON data
#     figure_dict = json.loads(data)
#
#     # Create Figure object from JSON data
#     fig = from_json(json.dumps(figure_dict))
#
#     st.plotly_chart(fig)

# @tool()
# def analyze(instruct:str, state:Annotated[State,InjectedState]):
#     """
#     Analyze or modify the data in the csv file user uploaded. (Translated instructions like '分析' should have same effect.)
#     Args:
#         instruct: String, the instruction of user, indicate how will the user operate or analyze the data table.
#     """
#     # 使用injected state 传入时要记得保证State中元素齐全
#     llm = get_llm(state["model"],state["api_key"])
#     df = pd.read_table(state["df_path"],sep=",")
#
#     path = os.path.dirname(state["df_path"])
#     prefix = (f"Every time you show a plot (plt.show()), you MUST save it in path: {path} in .png format. "+\
#               f"The dataframe is located at path: {state['df_path']}, NEVER fabricate a non-existing dataframe."+\
#               r"Use \n as line continuation character. If unexpected character after line continuation character error occurs, try to remove redundant backslash sign.")
#     print(state["messages"])
#     pd_agent = create_pandas_dataframe_agent(llm, df,
#                                   prefix=prefix,
#                                   allow_dangerous_code=True,
#                                   verbose=True,
#                                   agent_type="tool-calling",
#                                   max_execution_time=90,
#                                   return_intermediate_steps=True,
#                                   # extra_tools=save_plot
#                                  )
#     result = pd_agent.invoke(instruct)
#     print(result)
#     return result["output"]

@tool()
def analyze(instruct:str, state:Annotated[State,InjectedState]):
    """
    Analyze or modify the data in the csv file user uploaded. (Translated instructions like '分析' should have same effect.)
    Args:
        instruct: String, the instruction of user, indicate how will the user operate or analyze the data table.
    """
    # 使用injected state 传入时要记得保证State中元素齐全
    llm = get_llm(state["model"],state["api_key"])
    df = pd.read_table(state["df_path"],sep=",")

    path = os.path.dirname(state["df_path"])
    prefix = f"Every time you show a plot (plt.show()), you MUST save it in path: {path} in .png format. Be careful of 'unexpected character after line continuation character' error."

    pd_agent = create_pandas_dataframe_agent(llm, df,
                                  prefix=prefix,
                                  allow_dangerous_code=True,
                                  verbose=True,
                                  agent_type="tool-calling",
                                  return_intermediate_steps=True,
                                  # extra_tools=save_plot
                                 )
    result = pd_agent.invoke(instruct)
    return result["output"]


@tool()
def groupby(colname:str, target:str, state:Annotated[State,InjectedState]):
    """
    Group the data according to the given column name.
    Args:
        colname: the name of the column you need to aggregate.
        target: the name of the target column you want to calculate
    """
    df = pd.read_csv(state["df_path"],sep=";")

    result = df.groupby([colname])[target].sum().sort_values(ascending=False)
    return result

@tool()
def forget(state:Annotated[State,InjectedState]):
    """
    Forget the chat history ONLY IF the user said that.
    """
    messages = [RemoveMessage(id=m.id) for m in state["messages"]]
    return {"messages":messages}

tools = [analyze, forget]

class Form(BaseModel):
    """
    Your output MUST be in strict JSON format instead of dict format.
    """
    need_execute: bool = Field(description="Whether need to execute the analysis or not.")
    reply: str = Field(description="The text reply or translation")

class Node():
    def translator(state:State):
        # print("--> Translator")
        df = pd.read_table(state["df_path"], sep=",")
        messages = state['messages']
        translator = get_llm(state["model"],state["api_key"])
        translator = translator.bind(response_format={"type": "json_object"})
        translator = translator.with_structured_output(Form,strict=True)
        translator_prompt = f"""\
        # Common Case:
        ## Task: Your task is to translate the instruction of user to prompt that aligns with current context.\
        Convert user's intention to given tool and terms of given dataset.\n
        ## What you have:\
        - Name, description of each tool in the format of (tool_name,tool_description): {[(t.name,t.description) for t in tools]};\
        - Column names of given dataset: {df.columns.tolist()};\n
        ## You should return:\n
        - reply: generated translation according to the given dataset.(output result only)\n
        - need_execute: True\n
        
        # Rare Case:
        However, If chat history is enough to answer user's question / user's question is irrelevant to data analysis,\
        You should simply summary and reply.\
        
        # Response Format
        You MUST use the tool 'Form' to structure your result, output MUST be in JSON format (DO NOT output dict!)
        Directly give me your result based on following user instruction:
        """.replace("    ","")

        response = translator.invoke(set_prompt(messages, translator_prompt))
        print("Node: translator: ",response) if state["verbose"] else None
        return {"messages":[AIMessage(response.reply)],"need_execute":response.need_execute}

    def executor(state: State): # 对于任何一个node，它的输出需要是一个state
        # print("--> EXECUTOR")
        messages = state['messages']
        # print_messages(messages)
        executor = get_llm(state["model"],state["api_key"])
        executor = executor.bind_tools(tools)
        if type(messages[-1])!=ToolMessage:
            executor_prompt = "You should faithfully execute the steps given by previous plan."+\
            "In each step, use given columns in the dataset to call tools. Call tool if necessary."

            messages = set_prompt(messages, executor_prompt)
            # print_messages(messages)
            response = executor.invoke(messages[-2:])
        else:
            executor_prompt = "Translate the calculated result of tool to human language."+\
            "Do not output anything about running error, including unseen visual output or fail to execute."+\
            "Simply summarize the analyzed data."
            # 不能往AIMessage with tool_call和ToolMessage中间加东西！否则报错
            # print_messages(messages)
            response = executor.invoke(messages[-2:]+[SystemMessage(executor_prompt)])
        print("Node: executor: ", response) if state["verbose"] else None
        return {"messages": [response]}


class Route():
    def if_need_execute(state:State):
        if state["need_execute"]:
            return "continue"
        else:
            return "end"

    def if_tool(state: State):
        """判断executor是否生成了toolcall，是则调用tool"""
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return "end"

def build_graph():
    graph_builder = StateGraph(State)

    graph_builder.add_node("translator",Node.translator)
    graph_builder.add_node("executor", Node.executor)
    graph_builder.add_node("tools", ToolNode(tools))

    graph_builder.add_edge(START,"translator")
    graph_builder.add_conditional_edges("translator",Route.if_need_execute
                                        ,{"continue":"executor","end":END})
    # 使用path map来锁定输出的node
    graph_builder.add_conditional_edges("executor",Route.if_tool,
                                        {"tools":"tools","end":END},
                                        )
    graph_builder.add_edge("tools","executor")

    graph = graph_builder.compile(checkpointer=MemorySaver())
    print("graph compile done")
    return graph


