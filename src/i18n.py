"""Internationalization for awgctl.

Messages are injected at build time from lang/*.py.
For development, default (English) messages are used as fallbacks.
"""

MESSAGES = {}


def load_messages(messages_dict):
    """Load a message dictionary (called by build-generated bootstrap)."""
    global MESSAGES
    MESSAGES = messages_dict


def _t(key, **kwargs):
    """Translate a message key, applying optional format arguments."""
    msg = MESSAGES.get(key, key)
    if kwargs:
        try:
            return msg.format(**kwargs)
        except KeyError:
            return msg
    return msg
