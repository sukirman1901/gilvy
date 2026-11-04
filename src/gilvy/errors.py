"""Errors an agent can fix by editing the episode, not the renderer."""

from __future__ import annotations


class GilvyError(Exception):
    """A problem in an episode, a missing tool, or a failed encode."""

    def __init__(self, message, *, code="operation_failed", field=None):
        super().__init__(message)
        self.code = code
        self.field = field


class CaptionError(GilvyError):
    """A caption line is too long for the frame."""


class EpisodeError(GilvyError):
    """The YAML episode is missing a field or names an unknown scene."""

    def __init__(self, message, *, field=None):
        super().__init__(message, code="invalid_input", field=field)
