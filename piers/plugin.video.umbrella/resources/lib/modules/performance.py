"""Local, opt-in timings without request URLs, arguments, or account data."""
from time import monotonic


def record(kind, started, name='', outcome='complete'):
	# Diagnostics must never change the result of the operation being measured.
	try:
		from resources.lib.modules import control
		if control.setting('debug.enabled') != 'true' or control.setting('debug.level') != '1': return
		import os
		import re
		import threading
		from resources.lib.modules import log_utils
		name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)[:80]
		log_utils.log('BrowsePerf kind=%s name=%s outcome=%s elapsed_ms=%.1f pid=%s thread=%s' % (
			kind, name, outcome, max(0, monotonic() - started) * 1000,
			os.getpid(), threading.get_ident()), level=log_utils.LOGDEBUG)
	except Exception:
		pass
