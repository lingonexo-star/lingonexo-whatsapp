"""Fabrique des sources surveillées."""

from __future__ import annotations

from ..config import ConfigSource, Configuration
from ..http import ClientHttp
from .joradp import SourceJoradp
from .web import SourcePage, SourceRss


def construire_source(cfg: ConfigSource, http: ClientHttp, config: Configuration):
    if cfg.type == "joradp":
        return SourceJoradp(cfg, http, config)
    if cfg.type == "page":
        return SourcePage(cfg, http, config)
    if cfg.type in ("rss", "google_news"):
        return SourceRss(cfg, http, config)
    raise ValueError(f"Type de source inconnu : {cfg.type}")
