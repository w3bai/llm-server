import json
import os
from datetime import datetime
from typing import Optional
import uuid

class Competition:
    def __init__(self, id, name: str, github_url: str, docs_url: Optional[str] = None, created_at=None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.github_url = github_url
        self.docs_url = docs_url
        self.created_at = None or datetime.now().isoformat()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "github_url": self.github_url,
            "docs_url": self.docs_url,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            name=data["name"],
            github_url=data["github_url"],
            docs_url=data["docs_url"],
            created_at=data["created_at"]
        )

class CompetitionManager:
    def __init__(self, storage_file="competitions.json"):
        self.storage_file = storage_file
        self.competitions = {}
        self.load_competitions()

    def load_competitions(self):
        if os.path.exists(self.storage_file):
            with open(self.storage_file, "r") as f:
                data = json.load(f)
                self.competitions = {
                    id: Competition.from_dict(comp_data)
                    for id, comp_data in data.items()
                }

    def save_competitions(self):
        data = {
            id: comp.to_dict()
            for id, comp in self.competitions.items()
        }
        with open(self.storage_file, "w") as f:
            json.dump(data, f, indent=2)

    def create_competition(self, name, github_url, docs_url=None):
        competition = Competition(str(len(self.competitions) + 1), name, github_url, docs_url)
        self.competitions[competition.id] = competition
        self.save_competitions()
        return competition.id

    def get_competition(self, competition_id):
        return self.competitions.get(competition_id)

    def list_competitions(self):
        return list(self.competitions.values())

    def delete_competition(self, competition_id):
        if competition_id in self.competitions:
            del self.competitions[competition_id]
            self.save_competitions()
            return True
        return False

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "github_url": self.github_url,
            "docs_url": self.docs_url,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            name=data["name"],
            github_url=data["github_url"],
            docs_url=data["docs_url"],
            created_at=data["created_at"]
        )

class CompetitionManager:
    def __init__(self, storage_file="competitions.json"):
        self.storage_file = storage_file
        self.competitions = {}
        self.load_competitions()

    def load_competitions(self):
        if os.path.exists(self.storage_file):
            with open(self.storage_file, "r") as f:
                data = json.load(f)
                self.competitions = {
                    id: Competition.from_dict(comp_data)
                    for id, comp_data in data.items()
                }

    def save_competitions(self):
        data = {
            id: comp.to_dict()
            for id, comp in self.competitions.items()
        }
        with open(self.storage_file, "w") as f:
            json.dump(data, f, indent=2)

    def create_competition(self, name, github_url, docs_url=None):
        competition = Competition(str(len(self.competitions) + 1), name, github_url, docs_url)
        self.competitions[competition.id] = competition
        self.save_competitions()
        return competition.id

    def get_competition(self, competition_id):
        return self.competitions.get(competition_id)

    def list_competitions(self):
        return list(self.competitions.values())

    def delete_competition(self, competition_id):
        if competition_id in self.competitions:
            del self.competitions[competition_id]
            self.save_competitions()
            return True
        return False