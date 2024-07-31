from app.config import Config
import openai
import re
from typing import List
import ast
import tiktoken

class TextProcessor:
    def __init__(self):
        self.client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
        self.chunk_size = Config.CHUNK_SIZE
        self.chunk_overlap = Config.CHUNK_OVERLAP
        self.min_chunk_size = 100
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def estimate_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def chunk_text(self, text: str, is_code: bool = False) -> List[str]:
        if is_code:
            initial_chunks = self.chunk_code(text)
        else:
            initial_chunks = self.chunk_documentation(text)

        # Ensure chunks are within token limit
        max_tokens = 8000  # Leaving some buffer
        final_chunks = []
        for chunk in initial_chunks:
            if self.estimate_tokens(chunk) > max_tokens:
                sub_chunks = self.split_large_chunk(chunk, max_tokens)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)

        # Double-check and split any chunks that are still too large
        double_checked_chunks = []
        for chunk in final_chunks:
            if self.estimate_tokens(chunk) > max_tokens:
                double_checked_chunks.extend(self.split_large_chunk(chunk, max_tokens))
            else:
                double_checked_chunks.append(chunk)

        return double_checked_chunks

    def chunk_documentation(self, text: str) -> List[str]:
        # Split by markdown headers
        chunks = self.split_by_markdown_headers(text)
        
        # If no headers or chunks are too large, fall back to paragraph-based chunking
        if not chunks or any(len(chunk) > self.chunk_size for chunk in chunks):
            chunks = self.split_by_paragraphs(text)

        # Merge small chunks and split large ones
        return self.optimize_chunks(chunks)

    def split_by_markdown_headers(self, text: str) -> List[str]:
        pattern = r'^#{1,6}\s+.+$'
        lines = text.split('\n')
        chunks = []
        current_chunk = []

        for line in lines:
            if re.match(pattern, line) and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
            current_chunk.append(line)

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    def split_by_paragraphs(self, text: str) -> List[str]:
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def optimize_chunks(self, chunks: List[str]) -> List[str]:
        optimized_chunks = []
        current_chunk = []

        for chunk in chunks:
            if len('\n'.join(current_chunk)) + len(chunk) > self.chunk_size:
                if current_chunk:
                    optimized_chunks.append('\n'.join(current_chunk))
                    current_chunk = []
            current_chunk.append(chunk)

        if current_chunk:
            optimized_chunks.append('\n'.join(current_chunk))

        # Split any chunks that are still too large
        final_chunks = []
        for chunk in optimized_chunks:
            if len(chunk) > self.chunk_size:
                final_chunks.extend(self.split_large_chunk(chunk))
            elif len(chunk) >= self.min_chunk_size:
                final_chunks.append(chunk)

        return final_chunks

    def split_large_chunk(self, chunk: str, max_tokens: int = 7500) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+', chunk)
        sub_chunks = []
        current_sub_chunk = []

        for sentence in sentences:
            if self.estimate_tokens(' '.join(current_sub_chunk) + ' ' + sentence) > max_tokens:
                if current_sub_chunk:
                    sub_chunks.append(' '.join(current_sub_chunk))
                    current_sub_chunk = []
            current_sub_chunk.append(sentence)

        if current_sub_chunk:
            sub_chunks.append(' '.join(current_sub_chunk))

        # If any sub_chunk is still too large, split it by words
        word_split_chunks = []
        for sub_chunk in sub_chunks:
            if self.estimate_tokens(sub_chunk) > max_tokens:
                words = sub_chunk.split()
                current_word_chunk = []
                for word in words:
                    if self.estimate_tokens(' '.join(current_word_chunk) + ' ' + word) > max_tokens:
                        if current_word_chunk:
                            word_split_chunks.append(' '.join(current_word_chunk))
                            current_word_chunk = []
                    current_word_chunk.append(word)
                if current_word_chunk:
                    word_split_chunks.append(' '.join(current_word_chunk))
            else:
                word_split_chunks.append(sub_chunk)

        return word_split_chunks

    def chunk_code(self, code: str) -> List[str]:
        try:
            tree = ast.parse(code)
            chunks = self.get_code_chunks(tree, code)
        except SyntaxError:
            # For non-Python files, use a line-based approach
            chunks = self.chunk_code_by_lines(code)
        
        return self.optimize_chunks(chunks)

    def get_code_chunks(self, tree: ast.AST, code: str) -> List[str]:
        chunks = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                chunk = ast.get_source_segment(code, node)
                if chunk:
                    chunks.append(chunk)
        
        # Handle any remaining code not in functions or classes
        remaining_code = self.get_remaining_code(tree, code)
        if remaining_code:
            chunks.append(remaining_code)
        
        return chunks

    def get_remaining_code(self, tree: ast.AST, code: str) -> str:
        code_lines = code.split('\n')
        used_lines = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                start_line = node.lineno - 1
                end_line = node.end_lineno
                used_lines.update(range(start_line, end_line))

        remaining_lines = [line for i, line in enumerate(code_lines) if i not in used_lines]
        return '\n'.join(remaining_lines)

    def chunk_code_by_lines(self, code: str) -> List[str]:
        lines = code.split('\n')
        chunks = []
        current_chunk = []

        for line in lines:
            if len('\n'.join(current_chunk)) + len(line) > self.chunk_size - self.chunk_overlap:
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
            current_chunk.append(line)

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    def generate_embedding(self, text: str):
        if self.estimate_tokens(text) > 8000:
            raise ValueError(f"Text is too long ({self.estimate_tokens(text)} tokens). Maximum is 8000 tokens.")
        
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding