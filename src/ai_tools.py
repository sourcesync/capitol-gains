import openai
from dotenv import load_dotenv
import os

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

def chatgpt(prompt: str, model="gpt-4o", max_tokens=None) -> str:
    """OpenAI ChatGPT API wrapper for chat completions

    Args:
        prompt (str): The input text prompt
        model (str, optional): The model to use. Defaults to "gpt-4o". 
            options: ['gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo-preview', 'gpt-4-32k', 'gpt-4-1106-preview']
        max_tokens (int, optional): The maximum number of tokens to generate. Defaults to None.

    Returns:
        str: The response from the ChatGPT model
    """
    try:
        completion = openai_client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,  # 4000
            messages=[{"role": "user", "content": prompt}],
            timeout=15,
        )
    except openai.APITimeoutError:
        print("\nWARNING: ChatGPT request has timed out.\n")
        return None
    response = completion.choices[0].message.content
    return response