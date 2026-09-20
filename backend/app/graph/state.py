from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class SearchQueries(BaseModel):
    queries: list[str] = Field(
        description="Search queries to find relevant articles.",
        min_length=2,
        max_length=5,
    )


class Plan(BaseModel):
    article_count: int = Field(description="Number of articles to select.", ge=5, le=7)
    output_format: Literal["markdown", "html"] = Field(description="Newsletter output format.")


class Article(TypedDict):
    title: str
    url: str
    source: str
    published_at: str
    content: str
    summary: str


class ArticleSummary(BaseModel):
    url: str
    summary: str


class NewsletterDraft(BaseModel):
    subject: str
    content: str


class Review(BaseModel):
    feedback: str
    score: int = Field(ge=0, le=10)


class NewsletterState(TypedDict, total=False):
    goal: str
    mode: Literal["autonomous", "human"]

    plan: Plan

    search_queries: list[str]

    articles: list[Article]

    newsletter: str
    subject: str

    review_feedback: str
    review_score: int

    revision_count: int
    max_revisions: int
    approved: bool

    output_path: str
    sent: bool
