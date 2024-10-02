from github import Github, GithubException
from app.config import Config
import logging
import time
from urllib.parse import urlparse


class GitHubLoader:
    def __init__(self):
        self.github = Github(Config.GITHUB_TOKEN)
        self.logger = logging.getLogger(__name__)
        self.relevant_extensions = Config.GITHUB_RELEVANT_EXTENSIONS
        self.ignore_directories = Config.GITHUB_IGNORE_DIRECTORIES
        self.include_directories = Config.GITHUB_INCLUDE_DIRECTORIES
        self.rate_limit_delay = 1  # Delay in seconds between API calls

    def get_repo_contents(self, repo_url):
        try:
            repo_name = self._extract_repo_name(repo_url)
            repo = self.github.get_repo(repo_name)
            files = []
            dirs_to_process = [""]  # Start with the root directory

            while dirs_to_process:
                current_dir = dirs_to_process.pop(0)
                self._respect_rate_limit()
                contents = repo.get_contents(current_dir)

                for content in contents:
                    if content.type == "dir":
                        if self._should_process_directory(content.path):
                            dirs_to_process.append(content.path)
                    elif self._is_relevant_file(content):
                        files.append(content)

            self.logger.info(
                f"Found {len(files)} relevant files in repository {repo_name}"
            )
            return files
        except GithubException as e:
            self.logger.error(f"Error accessing repository {repo_url}: {str(e)}")
            raise

    def _extract_repo_name(self, repo_url):
        parsed_url = urlparse(repo_url)
        path_parts = parsed_url.path.strip("/").split("/")
        if len(path_parts) >= 2:
            return "/".join(path_parts[:2])
        else:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")

    def _should_process_directory(self, directory):
        path_parts = directory.split("/")
        return not any(
            ignore_dir in path_parts for ignore_dir in self.ignore_directories
        ) and any(include_dir in path_parts for include_dir in self.include_directories)

    def _is_relevant_file(self, file_content):
        if file_content.name == "README.md":
            return True

        if file_content.name.endswith(tuple(self.relevant_extensions)):
            return True

        return False

    def get_file_content(self, file):
        try:
            self._respect_rate_limit()
            return file.decoded_content.decode("utf-8")
        except UnicodeDecodeError:
            self.logger.warning(
                f"Unable to decode file content. File '{file.name}' may be a binary file."
            )
            return f"[Unable to decode file content. File '{file.name}' may be a binary file.]"

    def _respect_rate_limit(self):
        remaining, _ = self.github.rate_limiting
        if remaining <= 10:  # Arbitrary threshold, adjust as needed
            self.logger.warning("Approaching GitHub API rate limit. Sleeping...")
            time.sleep(self.rate_limit_delay)
