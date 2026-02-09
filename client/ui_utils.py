"""Shared UI helper utilities for CustomTkinter windows."""

from __future__ import annotations

import typing as _t

try:
	import customtkinter as ctk  # noqa: F401 - used for typing/side effects
except Exception:
	ctk = None  # pragma: no cover


def bring_window_to_front(window: _t.Any, release_delay: int = 400) -> None:
	"""Lift the given toplevel window so it appears in front of other apps.

	Args:
		window: Any Tk-compatible window that supports lift/focus/attributes.
		release_delay: Milliseconds to keep the window on top before releasing.
	"""

	if window is None:
		return

	def _release_topmost() -> None:
		try:
			window.attributes('-topmost', False)
		except Exception:
			pass

	try:
		window.lift()
		window.focus_force()
		window.attributes('-topmost', True)
		if release_delay and hasattr(window, 'after'):
			window.after(release_delay, _release_topmost)
		else:
			_release_topmost()
	except Exception:
		pass

