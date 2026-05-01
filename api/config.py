"""FastAPI configuration — reads from config/settings.yaml."""
import sys
from pathlib import Path

# Add project scripts to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "utils"))


class Settings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        import yaml
        settings_path = PROJECT_ROOT / "config" / "settings.yaml"
        with open(settings_path) as f:
            self.data = yaml.safe_load(f)
        self.project = self.data.get("project", {})
        self.db_config = self.data.get("database", {})
        self.model_configs = self.data.get("model", [])
        self.llm_limits = self.data.get("llm_limits", {})

    @property
    def db_type(self) -> str:
        return self.db_config.get("type", "sqlite")

    @property
    def project_name(self) -> str:
        return self.project.get("name", "Urban Signal Miner")


settings = Settings()
