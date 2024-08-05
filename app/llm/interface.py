from anthropic import Anthropic
from openai import OpenAI
from app.config import Config


class LLMInterface:
    def __init__(self):
        self.anthropic_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)

    def generate_response(
        self,
        system_prompt,
        human_prompt,
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0,
    ):
        if model.startswith("claude"):
            return self.generate_anthropic_response(
                system_prompt, human_prompt, model, max_tokens, temperature
            )
        elif model.startswith("gpt"):
            return self.generate_openai_response(
                system_prompt, human_prompt, model, max_tokens, temperature
            )
        else:
            raise ValueError(f"Unsupported model: {model}")

    def generate_anthropic_response(
        self, system_prompt, human_prompt, model, max_tokens, temperature
    ):
        response = self.anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": human_prompt}],
        )
        return response.content[0].text

    def generate_openai_response(
        self, system_prompt, human_prompt, model, max_tokens, temperature
    ):
        response = self.openai_client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": human_prompt},
            ],
        )
        return response.choices[0].message.content

    # You can add more methods for other models or providers as needed
