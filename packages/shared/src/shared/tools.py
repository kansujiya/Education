"""Typed I/O for tools that agents and MCP servers expose.

Every tool has a TypedInput/TypedOutput pair. The same pair is used by:
  - the in-process tool implementation,
  - the MCP server tool definition,
  - the Anthropic tool-use schema (auto-derived from these),
  - the unit tests.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from shared.models import SyllabusTopic

# ---- mcp-syllabus -----------------------------------------------------


class FetchSyllabusInput(BaseModel):
    exam_id: str = Field(..., description="Slug like 'aws-ccp' or 'gate-cse'.")


class FetchSyllabusOutput(BaseModel):
    exam_id: str
    name: str
    topics: list[SyllabusTopic]


class ParseSyllabusInput(BaseModel):
    raw: str = Field(..., description="Free-form syllabus markdown / text to parse.")
    exam_id: str


class ParseSyllabusOutput(BaseModel):
    topics: list[SyllabusTopic]


class DiffSyllabusInput(BaseModel):
    old: list[SyllabusTopic]
    new: list[SyllabusTopic]


class DiffSyllabusOutput(BaseModel):
    added: list[str]
    removed: list[str]
    renamed: list[tuple[str, str]]
