import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from github import Github
from app.config import Config
import logging


class GitHubLoader:
    def __init__(self):
        self.github = Github(Config.GITHUB_TOKEN)
        logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    def get_repo_contents(self, repo_url):
        logging.info(f"Fetching contents from repository: {repo_url}")
        repo = self.github.get_repo(repo_url.split("github.com/")[-1])
        files = []
        dirs_to_process = [""]  # Start with the root directory

        while dirs_to_process:
            current_dir = dirs_to_process.pop(0)
            contents = repo.get_contents(current_dir)

            for content in contents:
                if content.type == "dir":
                    dirs_to_process.append(content.path)
                elif self.is_relevant_file(content):
                    files.append(content)

        logging.info(f"Found {len(files)} relevant files")
        return files

    def is_relevant_file(self, file_content):
        relevant_extensions = (".sol", ".go", ".rs")
        ignored_dirs = [
            "libs",
            "lib",
            "test",
            "tests",
            "scripts",
            "node_modules",
            "dist",
        ]
        path_parts = file_content.path.split("/")

        # Ignore files in ignored directories
        if any(ignored_dir in path_parts for ignored_dir in ignored_dirs):
            return False

        # Include README.md in any directory
        if file_content.name == "README.md":
            logging.info(f"Relevant file found: {file_content.path}")
            return True

        # Include files with relevant extensions under 'src' or 'contracts' directories
        if "src" in path_parts or "contracts" in path_parts:
            if file_content.name.endswith(relevant_extensions):
                logging.info(f"Relevant file found: {file_content.path}")
                return True

        return False

    def get_file_content(self, file):
        try:
            return file.decoded_content.decode("utf-8")
        except UnicodeDecodeError:
            return f"[Unable to decode file content. File '{file.name}' may be a binary file.]"

    def format_repo_content(self, files):
        logging.info("Formatting repository content")
        output = "## Repository Structure\n```\n"
        dir_structure = set()

        for file in files:
            dir_structure.add(os.path.dirname(file.path))

        for dir in sorted(dir_structure):
            depth = len(dir.split("/")) - 1
            output += "  " * depth + (os.path.basename(dir) or ".") + "/\n"

        output += "```\n\n"

        for file in files:
            content = self.get_file_content(file)
            extension = os.path.splitext(file.name)[1][1:]  # remove the dot
            output += f"\n## {file.path}\n```{extension}\n{content}\n```\n"

        logging.info("Content formatting completed")
        return output

    def get_formatted_repo_content(self, repo_url):
        files = self.get_repo_contents(repo_url)
        return self.format_repo_content(files)


if __name__ == "__main__":
    loader = GitHubLoader()
    repo_url = "https://github.com/code-423n4/2024-07-karak"  # Add a GitHub repository URL here
    print(loader.get_formatted_repo_content(repo_url))
