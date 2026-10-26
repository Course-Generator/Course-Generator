"""Anemic domain models shared by the application layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TypeAlias

# A slide map is ``slide title -> bullet points``.
SlideMap: TypeAlias = Dict[str, List[str]]
# A lecture map is ``lecture name -> slide map``.
LectureMap: TypeAlias = Dict[str, SlideMap]
# A course map is ``lecture name -> slide map`` (alias kept for readability).
CourseMap: TypeAlias = LectureMap
# Narration is ``lecture name -> slide title -> audio clip paths``.
AudioMap: TypeAlias = Dict[str, Dict[str, List[str]]]


@dataclass
class UserAccount:
    id: str
    name: str
    email: str
    age: int
    gender: str
    password_hash: str
    salt: str = ""


@dataclass
class PendingRegistration:
    name: str
    email: str
    age: int
    gender: str
    password_hash: str
    salt: str


@dataclass
class Chapter:
    title: str
    start_page: int
    end_page: int


@dataclass
class PresentationStyle:
    title_font_size: int = 24
    content_font_size: int = 18
    font_name: str = "Arial"
    title_color: str = "#000000"
    content_color: str = "#000000"
    background_path: Optional[str] = None
    template: str = "Default"


@dataclass
class CourseArtifacts:
    course_name: str
    output_stem: str
    slides: LectureMap = field(default_factory=dict)
    presentation_slides: LectureMap = field(default_factory=dict)
    explanations: LectureMap = field(default_factory=dict)
    short_slides: LectureMap = field(default_factory=dict)
    text_chunks: List[str] = field(default_factory=list)
    audio_paths: AudioMap = field(default_factory=dict)
    video_path: Optional[str] = None
    video_link: Optional[str] = None
    presentation_path: Optional[str] = None
    presentation_link: Optional[str] = None
    conversation: object = None
    chat_history: List[object] = field(default_factory=list)


@dataclass
class MediaLibrary:
    videos: Dict[str, str] = field(default_factory=dict)
    presentations: Dict[str, str] = field(default_factory=dict)
