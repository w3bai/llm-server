# Web3 Audit Assistant

## Project Overview

Web3 Audit Assistant is an AI-powered tool designed to assist developers participating in Web3 smart contract audit contests. This system provides context-aware responses to questions about specific protocols, helping auditors understand codebases and identify potential areas of concern.

## Key Features

- **Dynamic Competition Management**: Supports multiple audit contests simultaneously, each with its own isolated context.
- **Automated Data Ingestion**: Automatically processes and indexes GitHub repositories and documentation for each competition.
- **AI-Powered Responses**: Utilizes Claude 3.5 Sonnet model to generate informed, context-specific answers to auditors' questions.
- **Semantic Search**: Employs OpenAI's text-embedding-3-small model and Pinecone vector database for efficient retrieval of relevant information.
- **RESTful API**: Offers a FastAPI-based interface for easy integration and scalability.

## Technology Stack

- **FastAPI**: Modern, fast (high-performance) web framework for building APIs with Python 3.7+
- **Anthropic Claude 3.5 Sonnet**: Large language model for generating responses
- **OpenAI Embeddings**: text-embedding-3-small for creating text embeddings
- **Pinecone**: Vector database for efficient similarity search
- **PyGithub**: For interacting with GitHub repositories
- **BeautifulSoup4**: For web scraping documentation

## Getting Started

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables in `.env` file
4. Run the application: `python run.py`

## Usage

- Create a new competition: `POST /competitions`
- List all competitions: `GET /competitions`
- Query the assistant: `POST /query`

For detailed API documentation, run the server and visit `http://localhost:8000/docs`.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.
