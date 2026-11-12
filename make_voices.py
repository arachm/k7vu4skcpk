"""Make the recordings of the app with Microsoft Azure neural voices.

Runs on GitHub (Actions), never on the phone. The Azure key comes from the repository
secrets and is never printed. Free tier (F0): 500,000 characters a month.
The free tier allows 20 recordings a minute, so the script paces itself.

Two ways to run it (Actions -> Make voices -> Run workflow, then type one word):
  sample   records the same short Czech text with EVERY voice that can speak Czech,
           so you can listen and choose voices (about 5 minutes).
  all      records everything in texts.json (10 = only the first 10, for a test).
  1/2      records the first half of texts.json, 2/2 the second half
           (big lists: run 1/2, wait until it has finished, then 2/2).

texts.json:  { "L1-0": ["Dobrý den!", "m"], ... }
  "m" = Antonín (Czech man), "f" = Vlasta (Czech woman),
  or the full name of another voice, e.g. "en-US-AndrewMultilingualNeural".
  An optional third value sets the speed, e.g. "+0%".

Single words are always recorded by Vlasta: slower, with a falling tone.
Every recording gets a little silence before and after, so nothing is cut off.
Since 12 Nov 2026 the sound is Opus at 24 kHz (clearer than the old 16 kHz mp3).
"""
import json, os, re, sys, time, urllib.request, urllib.error
from xml.sax.saxutils import escape

KEY, REGION = os.environ.get('KEY', '').strip(), os.environ.get('REGION', '').strip()
if not KEY or not REGION:
    sys.exit('Missing secrets: add AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in Settings → Secrets and variables → Actions.')
src, out = sys.argv[1], sys.argv[2]
mode = (sys.argv[3] if len(sys.argv) > 3 else 'all').strip().lower()
NATIVE = {'m': 'cs-CZ-AntoninNeural', 'f': 'cs-CZ-VlastaNeural'}
RATE = os.environ.get('RATE', '-5%')            # sentences: a little slower than normal speech
RATE_WORD = os.environ.get('RATE_WORD', '-20%') # one word: slow and clear
RATE_SHORT = os.environ.get('RATE_SHORT', '-10%')  # two or three words
FORMAT = os.environ.get('FORMAT', 'ogg-24khz-16bit-mono-opus')
EXT = '.ogg' if 'opus' in FORMAT else '.mp3'
PAUSE = float(os.environ.get('PAUSE', '3.1'))   # seconds per recording: stays under 20 a minute
BASE = f'https://{REGION}.tts.speech.microsoft.com/cognitiveservices'
os.makedirs(out, exist_ok=True)
SAMPLE = ('Dobrý den. Jmenuju se Klára a bydlím v Plzni. '
          'Prosím vás, kde je nádraží? Jeďte tramvají číslo čtyři. '
          'Dám si čaj a kousek čokoládového dortu. Děkuju, na shledanou!')


def ssml(text, voice, rate, word=False):
    body = f"<prosody rate='{rate}'>{escape(text)}</prosody>"
    if word:                                   # silence around single words, so nothing is cut off
        body = f"<break time='200ms'/>{body}<break time='350ms'/>"
    else:
        body = f"<break time='120ms'/>{body}<break time='250ms'/>"
    if not voice.startswith('cs-CZ-'):          # a foreign voice must be told to speak Czech
        body = f"<lang xml:lang='cs-CZ'>{body}</lang>"
    return (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='cs-CZ'>"
            f"<voice name='{voice}'>{body}</voice></speak>").encode('utf-8')


def post(data):
    req = urllib.request.Request(BASE + '/v1', data=data, method='POST', headers={
        'Ocp-Apim-Subscription-Key': KEY, 'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': FORMAT, 'User-Agent': 'cestina-obrazem'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def record(name, data, tries=8):
    """Send one request, wait and retry when Azure is busy. Returns True when saved."""
    for attempt in range(tries):
        try:
            audio = post(data)
            if len(audio) < 500: raise ValueError('audio too short')
            open(os.path.join(out, name + EXT), 'wb').write(audio)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 401: sys.exit('Azure says the key or region is wrong (401). Check the two secrets.')
            if e.code == 400: print(f'  {name}: Azure cannot make this one (400)'); return False
            wait = int(e.headers.get('Retry-After') or 0) or min(60, 5 * (attempt + 1))
            print(f'  {name}: HTTP {e.code}, waiting {wait} s'); time.sleep(wait)
        except Exception as e:
            print(f'  {name}: {type(e).__name__}, retrying'); time.sleep(5 * (attempt + 1))
    return False


def paced(fn):
    t0 = time.time(); ok = fn(); time.sleep(max(0.0, PAUSE - (time.time() - t0))); return ok


if mode == 'sample':
    req = urllib.request.Request(BASE + '/voices/list', headers={'Ocp-Apim-Subscription-Key': KEY, 'User-Agent': 'cestina-obrazem'})
    voices = json.load(urllib.request.urlopen(req, timeout=60))
    cz = [v for v in voices if v.get('Locale') == 'cs-CZ' or 'cs-CZ' in (v.get('SecondaryLocaleList') or [])]
    cz.sort(key=lambda v: (v.get('Locale') != 'cs-CZ', v.get('Gender', ''), v['ShortName']))
    print(f'{len(cz)} voices can speak Czech in region {REGION}.')
    lines = ['Number | voice | man/woman | type', '']
    for n, v in enumerate(cz, 1):
        short = v['ShortName']; who = 'woman' if v.get('Gender') == 'Female' else 'man'
        kind = 'Czech voice' if v.get('Locale') == 'cs-CZ' else 'foreign voice speaking Czech'
        nice = re.sub(r'[^A-Za-z0-9]+', ' ', v.get('LocalName') or v.get('DisplayName') or short).strip()
        fname = f'{n:02d} {nice} ({who})'
        ok = paced(lambda: record(fname, ssml(SAMPLE, short, RATE), tries=3))
        lines.append(f'{n:02d} | {short} | {who} | {kind}' + ('' if ok else ' | NOT AVAILABLE'))
        print(lines[-1], flush=True)
    open(os.path.join(out, 'list.txt'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('Finished. Download "voices" at the bottom of this page.')
    sys.exit(0)

texts = json.load(open(src, encoding='utf-8'))
items = list(texts.items())
if '/' in mode:
    k, n = (int(x) for x in mode.split('/')); size = -(-len(items) // n)
    items = items[(k - 1) * size: k * size]
    print(f'Part {k} of {n}: {len(items)} recordings, about {round(len(items) * PAUSE / 60)} minutes.', flush=True)
elif mode != 'all': items = items[:int(mode)]
done = failed = 0
for n, (i, entry) in enumerate(items, 1):
    text, v = entry[0], entry[1]
    words = len(text.split())
    word = words == 1
    if word: v = 'f'                                      # single words: always Vlasta, the clearest voice for one word
    voice = NATIVE.get(v, v)
    rate = entry[2] if len(entry) > 2 else (RATE_WORD if word else RATE_SHORT if words <= 3 else RATE)
    say = text + '.' if word and not re.search(r'[.!?…]$', text) else text   # falling tone, not a question
    if paced(lambda: record(i, ssml(say, voice, rate, word))): done += 1
    else: failed += 1; print(f'FAILED {i}: {text}')
    if n % 50 == 0: print(f'{n} / {len(items)} done', flush=True)
print(f'Finished: {done} recordings, {failed} failed.')
if failed > len(items) * 0.05: sys.exit('Too many failures.')
