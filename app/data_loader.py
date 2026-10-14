import re
from functools import lru_cache
from pathlib import Path

from app.models import Curriculum, OrgConfig, WorkflowTemplate

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_SAFE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def _config_path(kind: str, config_id: str) -> Path:
    if not _SAFE_ID.fullmatch(config_id):
        raise KeyError(config_id)
    path = DATA_DIR / kind / f"{config_id}.json"
    if not path.is_file():
        raise KeyError(config_id)
    return path


@lru_cache
def load_curriculum() -> Curriculum:
    path = DATA_DIR / "curriculum" / "vic-maths-l3-6.json"
    return Curriculum.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def load_template(template_id: str) -> WorkflowTemplate:
    path = _config_path("templates", template_id)
    return WorkflowTemplate.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache
def load_org(org_id: str) -> OrgConfig:
    path = _config_path("orgs", org_id)
    return OrgConfig.model_validate_json(path.read_text(encoding="utf-8"))


def list_orgs() -> list[OrgConfig]:
    return [load_org(p.stem) for p in sorted((DATA_DIR / "orgs").glob("*.json"))]
