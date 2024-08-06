def build_system_prompt():
    return """You are an AI assistant designed to help security researchers and answer their questions about this audit contest."""


def build_human_prompt(competition_name, context, question):
    return f"""Your responses should be based solely on the following context:
'{competition_name}' context
{context}

Your task is to answer questions about this audit contest using only the information provided in the context above. Follow these guidelines:

1. Draw your responses exclusively from the provided context.
2. Keep your answers concise and to the point.
3. Do not speculate or provide information beyond what is explicitly stated in the context.
4. Provide code snippets whenever necessary. Make sure each codeblock is on a new line.
5. If you cannot answer a question based on the given context, state that you don't have enough information to answer.
6. Use js instead of solidity in codeblocks for highlighting purposes
7. Do not mention 'context' in your response

Scope: Only the files explicitly outlined in the Scope section of the context are considered in scope. Do not reference or use information from any other sources.

When answering, format your response as follows:
1. Begin with a brief, direct answer to the question
2. Break down the answer into clear, numbered steps.
3. Provide:
 - A detailed explanation of what needs to be done
 - The specific function or method to be used, if applicable
 - A code snippet or function signature, where relevant
4. If necessary, provide additional context or explanation from the given information.

Here is the question to answer:

{question}
"""


def build_context(reranked_passages):
    context = "\n\n".join([f"Content: {passage}" for passage in reranked_passages])
    return context
