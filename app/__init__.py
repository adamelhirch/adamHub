# Ensures table models are imported before metadata creation.
from app import models as _models

__all__ = ["_models"]
