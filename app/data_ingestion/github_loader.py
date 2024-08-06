from github import Github
from app.config import Config


class GitHubLoader:
    def __init__(self):
        self.github = Github(Config.GITHUB_TOKEN)

    def get_repo_contents(self, repo_url):
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

        return files

    def is_relevant_file(self, file_content):
        relevant_extensions = (".sol", ".go", ".rs")
        path_parts = file_content.path.split("/")

        # Ignore files ending with 'report.md'
        if file_content.name.endswith("report.md"):
            return False

        # Check if the file is in the root directory
        if len(path_parts) == 1:
            return file_content.name.endswith("README.md")

        # Ignore files in the 'libs' directory or its subdirectories
        if (
            "libs" in path_parts
            or "lib" in path_parts
            or "test" in path_parts
            or "tests" in path_parts
        ):
            return False

        # Check if the file is under 'src' directory or its subdirectories
        if "src" in path_parts:
            return file_content.name.endswith(relevant_extensions)

        return False

    def get_file_content(self, file):
        try:
            return file.decoded_content.decode("utf-8")
        except UnicodeDecodeError:
            return f"[Unable to decode file content. File '{file.name}' may be a binary file.]"
