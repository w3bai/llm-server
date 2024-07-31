from github import Github
from app.config import Config

class GitHubLoader:
    def __init__(self):
        self.github = Github(Config.GITHUB_TOKEN)

    def get_repo_contents(self, repo_url):
        repo = self.github.get_repo(repo_url.split('github.com/')[-1])
        contents = repo.get_contents("src")
        files = []
        
        # Add root-level .md files
        root_contents = repo.get_contents("")
        for content in root_contents:
            if content.name.endswith('.md') and not content.name.endswith('-report.md'):
                files.append(content)

        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                if "test" not in file_content.path.lower():
                    contents.extend(repo.get_contents(file_content.path))
            else:
                if self.is_relevant_file(file_content):
                    files.append(file_content)
        return files

    def is_relevant_file(self, file_content):
        relevant_extensions = ('.sol', '.go', '.rs')
        return (
            file_content.name.endswith(relevant_extensions) and
            not file_content.name.endswith('-report.md') and
            "test" not in file_content.path.lower()
        )

    def get_file_content(self, file):
        try:
            return file.decoded_content.decode('utf-8')
        except UnicodeDecodeError:
            return f"[Unable to decode file content. File '{file.name}' may be a binary file.]"