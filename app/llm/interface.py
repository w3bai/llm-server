from anthropic import Anthropic
from app.config import Config

class LLMInterface:
    def __init__(self):
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    def generate_response(self, system_prompt, human_prompt, max_tokens=1000, temperature=0.35):
        response = self.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": human_prompt
                }
            ]
        )
        return response.content[0].text