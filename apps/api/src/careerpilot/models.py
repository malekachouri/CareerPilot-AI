"""Imports every ORM model so metadata is complete (Alembic autogenerate, mapper configuration)."""

from careerpilot.modules.assessments import models as assessments_models
from careerpilot.modules.coach import models as coach_models
from careerpilot.modules.content import models as content_models
from careerpilot.modules.kb import models as kb_models
from careerpilot.modules.taxonomy import models as taxonomy_models
from careerpilot.modules.users import models as users_models

__all__ = [
    "assessments_models",
    "coach_models",
    "content_models",
    "kb_models",
    "taxonomy_models",
    "users_models",
]
