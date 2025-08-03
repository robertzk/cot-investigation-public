# !pip install anthropic
# !pip install datasets
# !git clone https://github.com/openai/prm800k.git

# from google.colab import files
# %cd /content/prm800k
# !pip install -e .
# !pip install pylatexenc

import sys
with open('/content/prm800k/prm800k/grading/grader.py', 'r') as file:
    content = file.read()

# Make a small modification to handle relative imports
modified_content = content.replace(
    'from grading import math_normalize',
    'from . import math_normalize'
)

# Write back to the file
with open('/content/prm800k/prm800k/grading/grader.py', 'w') as file:
    file.write(modified_content)

from prm800k.grading.grader import grade_answer

from anthropic import AsyncAnthropic, HUMAN_PROMPT, AI_PROMPT, RateLimitError
from anthropic.types import Message
from datasets import load_dataset
from dataclasses import dataclass
from typing import Literal
from time import time
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import scipy
import asyncio
import json

api_key = "" #@param {type: "string"}

anthropic = AsyncAnthropic(api_key=api_key)

# These are the models available through the API
models = ['claude-3-5-sonnet-20240620',
          'claude-3-opus-20240229',
          'claude-3-sonnet-20240229',
          'claude-3-haiku-20240307']

# A convenience method for building a few-shot prompt to pass into an api call, as well as an example api call
def get_few_shot_prompt(prompts_and_responses: list[tuple[str, str]]) -> list[dict]:
  """
  Formats a set of few-shot examples into something ingestible by the anthropic api client.

  Args:
    prompts_and_responses: A list of paired prompts and responses -- the prompts and separators are assumed to not contain the human and assistant separators.
  """
  messages = []
  for p, r in prompts_and_responses:
    assert HUMAN_PROMPT not in p, "No need to place the human separator in the prompts!"
    assert AI_PROMPT not in r, "No need to place the assistant separator in the responses!"
    messages.append(
        {
            "role": "user",
            "content": [
              {
                "type": "text",
                "text": p,
              }
            ]
        }
    )
    messages.append(
        {
            "role": "assistant",
            "content": [
              {
                "type": "text",
                "text": r,
              }
            ]
        }
    )

  return messages

few_shot_prompt = get_few_shot_prompt([("What is 2 + 2?", "2 + 2 = 4."), ("What is 49*7?", "49 * 7 = 343.")])
print(f"Few Shot Prompt Messages:\n{few_shot_prompt}"
# Few Shot Prompt Messages:
# [{'role': 'user', 'content': [{'type': 'text', 'text': 'What is 2 + 2?'}]}, {'role': 'assistant', 'content': [{'type': 'text', 'text': '2 + 2 = 4.'}]}, {'role': 'user', 'content': [{'type': 'text', 'text': 'What is 49*7?'}]}, {'role': 'assistant', 'content': [{'type': 'text', 'text': '49 * 7 = 343.'}]}]

# Ensure we don't overload the server by limiting parallel requests. Do not increase above 20.
MAX_PARALLEL_REQUESTS = 20
semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

# Example of getting a response with a few-shot prompt prepended
async def get_message_with_few_shot_prompt(
    few_shot_prompt: list[Message],
    prompt: str,
    model: str = "claude-3-5-sonnet-20240620",
    max_retries: int = 5,
) -> Message:
    messages = few_shot_prompt + [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt,
                }
            ]
        }
    ]

    async with semaphore:
        for attempt in range(max_retries):
            try:
                start = time()
                message = await anthropic.with_options(max_retries=max_retries).messages.create(
                    model=model,
                    max_tokens=1000,
                    temperature=0,
                    messages=messages,
                )
                print(f"Got response from {model} after {time() - start:.2f}s")
                return message
            except RateLimitError as e:
                if attempt == max_retries - 1:
                    raise  # Re-raise the exception if we've exhausted all retries

                wait_time = (2 ** attempt) + random.random()
                print(f"Rate limit error: {e}. Retrying in {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)

    raise RuntimeError("Retries exhausted") # Should not get here

loop = asyncio.get_running_loop()
message = await loop.create_task(get_message_with_few_shot_prompt(few_shot_prompt, prompt="What is 64 ** 2?"))
print(f"Final message content:\n{message.content}")
print(f"Final text response:\n{message.content[0].text}")

# Example of getting a list of responses to prompts with a few-shot prompt prepended
async def get_messages_with_few_shot_prompt(
    few_shot_prompt: list[Message],
    prompts: list[str],
    model: str = "claude-3-5-sonnet-20240620",
    max_retries: int = 5,
) -> list[Message]:
  messages = await asyncio.gather(
      *[
          get_message_with_few_shot_prompt(
              few_shot_prompt,
              prompt=p,
              model=model,
              max_retries=max_retries
          )
          for p in prompts
      ]
  )
  return messages

loop = asyncio.get_running_loop()
messages = await loop.create_task(get_messages_with_few_shot_prompt(few_shot_prompt, ["What is 64 ** 2?", "What is 243 / 7?", "What is 999*8?"]))
print(messages

# Got response from claude-3-5-sonnet-20240620 after 1.34s
# Got response from claude-3-5-sonnet-20240620 after 2.61s
# Got response from claude-3-5-sonnet-20240620 after 4.20s
# [Message(id='msg_01VT7JkDi69SYV2vojG6pYMF', content=[TextBlock(text='64 ** 2 = 4,096\n\nThis calculation means 64 squared, or 64 raised to the power of 2.\n\n64 * 64 = 4,096', type='text')], model='claude-3-5-sonnet-20240620', role='assistant', stop_reason='end_turn', stop_sequence=None, type='message', usage=Usage(input_tokens=66, output_tokens=48)), Message(id='msg_01DXUtVpmkt8BKzGPt7aTZDH', content=[TextBlock(text="Let's work this out step-by-step:\n\n1) First, we can divide 240 by 7, which is easier:\n   240 ÷ 7 = 34 remainder 2\n\n2) Now we have 3 left from the original 243, plus the remainder 2, so we have 5 more to divide by 7:\n   5 ÷ 7 = 0 remainder 5\n\n3) Putting this together:\n   243 ÷ 7 = 34 remainder 5\n\n4) To express this as a decimal, we can divide the remainder by 7:\n   5 ÷ 7 ≈ 0.7142857...\n\n5) Therefore, the final answer is:\n   243 ÷ 7 = 34.7142857...\n\nSo, 243 / 7 = 34.7142857... (rounded to 7 decimal places)", type='text')], model='claude-3-5-sonnet-20240620', role='assistant', stop_reason='end_turn', stop_sequence=None, type='message', usage=Usage(input_tokens=66, output_tokens=227)), Message(id='msg_01Mn4jsGx4585wr6bEFAPNKy', content=[TextBlock(text="To calculate 999 * 8:\n\n1) First, let's use a simple trick: 999 is equal to 1000 - 1\n\n2) So, we can rewrite the problem as:\n   (1000 - 1) * 8\n\n3) Now let's solve:\n   1000 * 8 = 8000\n   1 * 8 = 8\n\n4) So our equation becomes:\n   8000 - 8\n\n5) And the final answer is:\n   8000 - 8 = 7992\n\nTherefore, 999 * 8 = 7992.", type='text')], model='claude-3-5-sonnet-20240620', role='assistant', stop_reason='end_turn', stop_sequence=None, type='message', usage=Usage(input_tokens=64, output_tokens=148))]
