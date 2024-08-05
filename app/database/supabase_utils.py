from supabase import create_client, Client
from app.config import Config
from typing import Optional, List, Dict


class SupabaseManager:
    def __init__(self):
        self.supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    def create_competition(
        self, name: str, github_url: str, docs_url: Optional[str] = None
    ) -> Dict:
        data = {"name": name, "github_url": github_url, "docs_url": docs_url}
        response = self.supabase.table("competitions").insert(data).execute()
        return response.data[0] if response.data else None

    def get_competition(self, competition_id: str) -> Dict:
        response = (
            self.supabase.table("competitions")
            .select("*")
            .eq("id", competition_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def list_competitions(self) -> List[Dict]:
        response = self.supabase.table("competitions").select("*").execute()
        return response.data

    def update_competition(self, competition_id: str, data: Dict) -> Dict:
        response = (
            self.supabase.table("competitions")
            .update(data)
            .eq("id", competition_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def delete_competition(self, competition_id: str) -> bool:
        response = (
            self.supabase.table("competitions")
            .delete()
            .eq("id", competition_id)
            .execute()
        )
        return len(response.data) > 0


supabase_manager = SupabaseManager()
