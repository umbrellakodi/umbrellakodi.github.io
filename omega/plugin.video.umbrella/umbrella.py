# -*- coding: utf-8 -*-
"""
	Umbrella Add-on
"""

import sys
from time import monotonic
invocation_started = monotonic()
from resources.lib.modules import router
from xbmc import getInfoLabel
if __name__ == '__main__':
	from resources.lib.modules import performance
	from urllib.parse import parse_qsl
	started = monotonic()
	performance.record('bootstrap', invocation_started)
	outcome = 'failed'
	try:
		router.router(sys.argv[2])
		outcome = 'complete'
	finally:
		# Only log a short action identifier; never include URLs or other params.
		action = dict(parse_qsl(sys.argv[2].lstrip('?'))).get('action', 'root')
		if not action.isidentifier() or len(action) > 80: action = 'other'
		performance.record('route', started, action, outcome)
		performance.record('invocation', invocation_started, action, outcome)
	if 'umbrella' not in getInfoLabel('Container.PluginName'): sys.exit(1) #TikiPeter RLI-Fix Test
