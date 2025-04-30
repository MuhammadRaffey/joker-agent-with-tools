from agents import Agent,Runner,OpenAIChatCompletionsModel,AsyncOpenAI,RunConfig
from openai.types.responses import ResponseTextDeltaEvent
from dotenv import load_dotenv,find_dotenv
import os
import chainlit as cl
from langsmith.wrappers import wrap_openai
from langsmith import traceable

# Load environment variables from .env file
_:bool=load_dotenv(find_dotenv())

GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")


client=wrap_openai(AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
))
model=OpenAIChatCompletionsModel(
    model="gemini-2.0-flash", #gemini-2.5-flash-preview-04-17 is slow
    openai_client=client,
)
config=RunConfig(
    model=model,
    model_provider=client,
    tracing_disabled=True,
)

joker=Agent(
    name="Joker",
    instructions="You Respond in Very Well Written Markdown, You have a Funny and Sarcastic Personality.",
)
@cl.on_chat_start
async def start_chat():
    cl.user_session.set("messages", [])
    await cl.Message("Welcome! I'm Joker.").send()

@traceable
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
