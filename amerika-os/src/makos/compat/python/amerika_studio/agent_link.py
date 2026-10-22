"""The removed Agent integration is deliberately unavailable in MakOS."""
from .common import StudioError

def set_agent_tools(enabled, paths=None):
    raise StudioError('This integration was removed from MakOS.', 'removed')
