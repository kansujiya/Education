"""Loaders that bring external data (syllabus, PYQs, ...) into the DB."""

from api.loaders.syllabus import SyllabusLoader, load_exam_via_mcp

__all__ = ["SyllabusLoader", "load_exam_via_mcp"]
