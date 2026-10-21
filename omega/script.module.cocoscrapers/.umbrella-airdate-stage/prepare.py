from pathlib import Path
import shutil
src=Path('../plugin.video.umbrella')
dst=Path('.umbrella-airdate-stage')
files=['resources/lib/modules/source_utils.py','resources/lib/modules/sources.py','resources/lib/modules/player.py']
files += ['resources/lib/debrid/'+name+'.py' for name in ('realdebrid','premiumize','alldebrid','offcloud','torbox','easydebrid')]
files += ['resources/lib/cloud_scrapers/'+name+'_cloud.py' for name in ('rd','pm','ad','oc','tb')]
for name in files:
 p=dst/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src/name,p)
p=dst/'resources/lib/modules/source_utils.py';s=p.read_text(encoding='utf-8')
pos=s.index('def seas_ep_filter(')
s=s[:pos]+'''def episode_airdate_pattern(premiered):
	"""Validate the selected episode's date and match common release separators."""
	from datetime import datetime
	if not isinstance(premiered, str) or not re.fullmatch(r'\\d{4}[-.]\\d{2}[-.]\\d{2}', premiered): return None
	try:
		date = datetime.strptime(premiered.replace('.', '-'), '%Y-%m-%d')
	except ValueError:
		return None
	return r'(?<!\\d)' + r'[. -]'.join(date.strftime('%Y.%m.%d').split('.')) + r'(?!\\d)'


'''+s[pos:]
s=s.replace('def seas_ep_filter(season, episode, release_title, split=False):','def seas_ep_filter(season, episode, release_title, split=False, premiered=None):',1)
marker='\t\tseason = str(season)'
pos=s.index(marker,s.index('def seas_ep_filter('))
s=s[:pos]+'''		# Inspect only the filename: a dated parent folder must not select another file.
		filename = release_title.replace('\\\\', '/').rsplit('/', 1)[-1]
		date_in_name = re.search(r'(?<!\\d)\\d{4}[.-]\\d{2}[.-]\\d{2}(?!\\d)', filename)
		if date_in_name:
			date_pattern = episode_airdate_pattern(premiered)
			date_match = re.search(date_pattern, filename) if date_pattern else None
			if date_match:
				return filename[date_match.end():] if split else True
			# A supplied date must agree; without one require explicit episode notation.
			if date_pattern or not re.search(r'(?:s\\d+[.-]?e|\\d+x\\d+|episode[.-]?\\d+)', filename):
				return None if split else False
'''+s[pos:]
p.write_text(s,encoding='utf-8')
# Keep existing positional calls valid by appending the optional date parameter.
for p in (dst/'resources/lib/debrid').glob('*.py'):
 s=p.read_text(encoding='utf-8')
 lines=s.splitlines(keepends=True)
 for i,line in enumerate(lines):
  if '\tdef resolve_magnet(' in line or '\tdef name_check(' in line:
   lines[i]=line.replace('):', ', premiered=None):')
  elif 'seas_ep_filter(' in line:
   # All matching calls have three positional arguments and optional split=True.
   import ast
   expr=ast.parse(line.strip()) if not line.lstrip().startswith(('if ','return ')) else None
 # AST positions allow nested path expressions and comprehension calls to be updated safely.
 s=''.join(lines)
 tree=__import__('ast').parse(s);ls=s.splitlines(keepends=True);offs=[0]
 for l in ls:offs.append(offs[-1]+len(l))
 edits=[]
 for n in __import__('ast').walk(tree):
  if isinstance(n,__import__('ast').Call) and isinstance(n.func,__import__('ast').Name) and n.func.id=='seas_ep_filter':
   row=n.end_lineno-1; col=len(ls[row].encode('utf-8')[:n.end_col_offset].decode('utf-8'));pos=offs[row]+col-1
   edits.append(pos)
 for pos in sorted(edits,reverse=True):s=s[:pos]+', premiered=premiered'+s[pos:]
 p.write_text(s,encoding='utf-8')
p=dst/'resources/lib/modules/sources.py';s=p.read_text(encoding='utf-8')
s=s.replace("url = debrid_function().resolve_magnet(url, item['hash'], season, episode, title)", "premiered = meta.get('premiered') or meta.get('firstaired') if isinstance(meta, dict) else None\n\t\t\t\t\turl = debrid_function().resolve_magnet(url, item['hash'], season, episode, title, premiered=premiered)",1)
s=s.replace('source_utils.seas_ep_filter(season, episode, release_title)', "source_utils.seas_ep_filter(season, episode, release_title, premiered=meta.get('premiered') or meta.get('firstaired'))")
p.write_text(s,encoding='utf-8')
p=dst/'resources/lib/modules/player.py';s=p.read_text(encoding='utf-8')
s=s.replace('def get(self, title, year, imdb, season, episode):','def get(self, title, year, imdb, season, episode, premiered=None):',1)
s=s.replace('def downloadForPlayNext(self,  title, year, imdb, season, episode, media_length):','def downloadForPlayNext(self,  title, year, imdb, season, episode, media_length, premiered=None):',1)
s=s.replace("seas_ep_filter(season, episode, j['fileName'])", "seas_ep_filter(season, episode, j['fileName'], premiered=premiered)")
s=s.replace('seas_ep_filter(season, episode, sFileName.lower())','seas_ep_filter(season, episode, sFileName.lower(), premiered=premiered)')
s=s.replace('Subtitles().get(self.title, self.year, self.imdb, self.season, self.episode)', "Subtitles().get(self.title, self.year, self.imdb, self.season, self.episode, premiered=self.meta.get('premiered') or self.meta.get('firstaired'))")
s=s.replace('Subtitles().downloadForPlayNext(self.title, self.year, self.imdb, self.season, self.episode, self.media_length)', "Subtitles().downloadForPlayNext(self.title, self.year, self.imdb, self.season, self.episode, self.media_length, premiered=self.meta.get('premiered') or self.meta.get('firstaired'))")
p.write_text(s,encoding='utf-8')
# Cloud providers already combine numbered patterns with a show-title check.
for p in (dst/'resources/lib/cloud_scrapers').glob('*.py'):
 s=p.read_text(encoding='utf-8')
 s=s.replace('from resources.lib.modules.source_utils import supported_video_extensions', 'from resources.lib.modules.source_utils import supported_video_extensions, episode_airdate_pattern',1)
 line="\t\t\tquery_list = self.episode_query_list() if 'tvshowtitle' in data else self.year_query_list()"
 assert line in s
 s=s.replace(line,line+"\n\t\t\tdate_pattern = episode_airdate_pattern(data.get('premiered')) if 'tvshowtitle' in data else None\n\t\t\tif date_pattern: query_list.append(date_pattern)",1)
 p.write_text(s,encoding='utf-8')
for p in dst.rglob('*.py'):compile(p.read_text(encoding='utf-8-sig'),str(p),'exec')
print('Staged and syntax-checked',len(files),'Umbrella files.')
