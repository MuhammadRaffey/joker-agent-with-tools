from agents import (
    Agent, 
    Runner, 
    RunConfig,
    AsyncOpenAI,
    OpenAIResponsesModel,
    WebSearchTool
    )
from dotenv import load_dotenv,find_dotenv
import os
import chainlit as cl
from openai.types.responses import ResponseTextDeltaEvent
from pdfTool import pdf_creator_tool
from agents.extensions.visualization import draw_graph


_:bool = load_dotenv(find_dotenv())

BASE_URL = "https://api.openai.com/v1"
MODEL = "gpt-4.1-mini"

# Load environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY is None:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.")

client=AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url=BASE_URL,
)
model=OpenAIResponsesModel(
    model=MODEL,
    openai_client=client,
)
config=RunConfig(
    model=model,
    model_provider=client
)

joker=Agent(
    name="Joker",
    instructions="You Respond in Very Well Written Markdown. You are a Joker that Tells Jokes about Gaming to the user you prefer the Game Pubg and you hate Free Fire and you make bad and dark jokes about ppl who play free fire and you love to play pubg and you are a pro player in pubg. You have access to the internet and you can search for information.When Someone ask you about weather ask that you ask if they play pubg or free fire and wait for thier response like finish your message after asking and if they play free fire you make fun of them and tell them to play pubg instead and also make a  joke about the weather like do not tell em what the weather is like. and if the user plays pubg you tell them the weather AFTER SEARCHING IT  and make a joke about it in pubg language. You also have a pdf creator Tool when a user asks you to create pdf you create em a pdf and give em the link",
    tools=[WebSearchTool(),pdf_creator_tool],
)
# draw_graph(joker,filename="agent_graph")  # gives error "Error reloading module: failed to execute WindowsPath('dot'), make sure the Graphviz executables are on your systems' PATH" on windows
@cl.on_chat_start
async def start_chat():
    cl.user_session.set("messages", [])
    await cl.Message("Welcome! I'm Joker, your gaming companion. Ask me anything, but first, tell me—do you play PUBG or Free Fire?").send()

@cl.on_message
async def handle_message(message: cl.Message):
    msg=cl.user_session.get("messages",[])
    msg.append({"role":"user","content":message.content})
    ai_msg=cl.Message(content="")
    result=Runner.run_streamed(
        joker,
        msg,
        run_config=config,
    )
    async for e in result.stream_events():
        if e.type=="raw_response_event"  and isinstance(e.data,ResponseTextDeltaEvent):
            token=e.data.delta
            await ai_msg.stream_token(token)
    msg.append({"role": "assistant", "content": result.final_output})
    cl.user_session.set("messages", msg)
