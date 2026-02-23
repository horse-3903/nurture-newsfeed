from dataclasses import dataclass


@dataclass
class Announcement:
    id: str
    title: str
    link: str
    source_id: str | None = None
    author: str | None = None
    description: str | None = None
    pub_date_raw: str | None = None
    pub_date: str | None = None
