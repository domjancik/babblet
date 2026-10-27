"""Bounded, display-independent transcript and translation lifecycle."""
import asyncio
import copy
import time
from collections import OrderedDict, deque

from babblet.languages import validate_targets
from babblet.tablet import TabletPresentation

LANGUAGES = {'en': 'English', 'he': 'Hebrew', 'ru': 'Russian'}


def route_language(text, detected):
    if detected not in {'en', 'he', 'ru'}:
        return detected
    counts = {'he': 0, 'ru': 0, 'en': 0}
    for char in text:
        if '\u0590' <= char <= '\u05ff' and char.isalpha():
            counts['he'] += 1
        elif '\u0400' <= char <= '\u04ff' and char.isalpha():
            counts['ru'] += 1
        elif char.isascii() and char.isalpha():
            counts['en'] += 1
    winner = max(counts, key=counts.get)
    total = sum(counts.values())
    return winner if total >= 3 and counts[winner] / total > 0.6 else detected


class Pipeline:
    def __init__(self, translator, *, max_pending=12, max_age=8, history=100,
                 retries=1, timeout=20, targets=None):
        if min(max_pending, max_age, history, timeout) <= 0:
            raise ValueError('Limits must be positive')
        self.translator = translator
        self.max_pending, self.max_age, self.history = max_pending, max_age, history
        self.retries, self.timeout = retries, timeout
        self.items = OrderedDict()
        self.jobs = deque()
        self.sequence = 0
        self.health = {'completed': 0, 'errors': 0, 'expired': 0, 'dropped': 0}
        self.processing = False
        self.active_translation = None
        self.closed = False
        self.targets = validate_targets(targets if targets is not None else LANGUAGES)
        self.tablet=TabletPresentation()
        self.display_index=0

    @property
    def pending(self):
        return len(self.jobs)

    def snapshot(self):
        return copy.deepcopy({'sequence': self.sequence,
            'selected_languages': list(self.targets),
            'utterances': list(self.items.values()),
            'health': {**self.health, 'pending': self.pending,
                       'processing': self.processing}})

    def _finish(self, job, status, text=None):
        uid, target, _, _, revision = job
        if not self._current(job):
            return False
        self.items[uid]['translations'][target] = {'status': status, 'text': text}
        self.tablet.publish(self.items[uid])
        self.sequence += 1
        return True

    def _current(self, job):
        uid, target, _, _, revision = job
        return (uid in self.items and self.items[uid]['revision'] == revision
                and target in self.targets)

    def _schedule(self, uid):
        item = self.items[uid]
        if item.get('display_only'):
            return
        text, language = item['source_text'], item['source_language']
        for target in self.targets:
            # A named output is always generated for that target language. A
            # mistaken ASR language label must never turn it into a raw transcript.
            if item['translations'].get(target, {}).get('status') != 'complete':
                while len(self.jobs) >= self.max_pending:
                    self._finish(self.jobs.popleft(), 'skipped')
                    self.health['dropped'] += 1
                previous = item['translations'].get(target, {}).get('text')
                item['translations'][target] = {'status': 'pending', 'text': previous}
                self.jobs.append((uid, target, time.monotonic(), (text, language), item['revision']))

    def set_phase(self, uid, phase):
        if uid in self.items:
            self.items[uid]['phase'] = phase
            self.tablet.publish(self.items[uid])
            self.sequence += 1

    def discard(self, receipts):
        """Forget completed display content, including queued translations.

        Revision checks protect a draft that changed while the page was turning.
        """
        discarded = []
        for receipt in receipts:
            uid = receipt['utterance_id']
            item = self.items.get(uid)
            if (item and item['revision'] == receipt['revision']
                    and item['phase'] in ('final','unrefined')):
                consumed = receipt.get('consumed')
                if consumed:
                    if any(value['status']=='pending' for value in item['translations'].values()):
                        continue
                    for code,count in consumed.items():
                        if code in item['translations'] and count>=0:
                            value=item['translations'][code]
                            if value.get('text') is not None:
                                value['text']=value['text'][count:]
                    if '_spoken' in consumed:
                        item['source_text']=item['source_text'][consumed['_spoken']:]
                    elif item['source_language'] in consumed:
                        # Compatibility with page receipts from the old layout.
                        item['source_text']=item['source_text'][consumed[item['source_language']]:]
                    else:
                        item['source_text']=''
                    item['display_only']=True
                    item['revision']+=1
                    self.sequence+=1
                    if item['source_text'] or any(value.get('text') for value in item['translations'].values()):
                        continue
                self.tablet.retire(uid)
                del self.items[uid]
                discarded.append(uid)
        if discarded:
            removed = set(discarded)
            self.jobs = deque(job for job in self.jobs if job[0] not in removed)
            self.sequence += 1
        return discarded

    async def revise(self, uid, text, language, start, end, phase='final'):
        if uid not in self.items:
            return await self.submit(uid, text, language, start, end, phase=phase)
        text = text.strip()
        if not text:
            return False
        item = self.items[uid]
        language = route_language(text, language)
        if text == item['source_text'] and language == item['source_language']:
            self.set_phase(uid, phase)
            return True
        self.jobs = deque(job for job in self.jobs if job[0] != uid)
        item.update(source_text=text, source_language=language, start=start, end=end,
                    phase=phase, revision=item['revision']+1, translations={})
        self._schedule(uid)
        self.tablet.publish(item)
        self.sequence += 1
        return True

    async def set_targets(self, targets):
        targets = validate_targets(targets)
        if targets == self.targets:
            return
        self.targets = targets
        self.jobs.clear()
        for uid, item in self.items.items():
            item['revision'] += 1
            item['translations'] = {code:value for code,value in item['translations'].items()
                                    if code in targets and value['status'] in ('source','complete')}
            for code in targets:
                item['translations'].setdefault(code, {'status':'skipped','text':None})
        # Backfill two recent paragraphs; keep a large history from flooding live work.
        for uid in list(self.items)[-2:]:
            self._schedule(uid)
        for item in self.items.values():
            self.tablet.publish(item)
        self.sequence += 1

    async def submit(self, uid, text, language, start, end, phase='final'):
        text = text.strip()
        if not text or uid in self.items:
            return False
        language = route_language(text, language)
        self.display_index+=1
        self.items[uid] = {'utterance_id': uid, 'source_text': text,
            'source_language': language, 'start': start, 'end': end,
            'speaker_id': None, 'translations': {}, 'phase':phase, 'revision':1,
            'display_index':self.display_index}
        self._schedule(uid)
        self.tablet.publish(self.items[uid])
        while len(self.items) > self.history:
            self.items.popitem(last=False)
        self.sequence += 1
        return True

    async def drain(self):
        # One consumer owns the model; never start one instance per language.
        if self.processing or not self.jobs:
            return
        self.processing = True
        try:
            while self.jobs:
                job = self.jobs.popleft()
                uid, target, queued, (text, language), revision = job
                if not self._current(job):
                    continue
                if uid not in self.items or time.monotonic() - queued > self.max_age:
                    self._finish(job, 'expired')
                    self.health['expired'] += 1
                    continue
                self.active_translation={'target':target,'utterance_id':uid,'started':time.monotonic()}
                for attempt in range(self.retries + 1):
                    try:
                        result = await asyncio.wait_for(
                            self.translator.translate(text, language, target), self.timeout)
                        if not result.strip():
                            raise ValueError('Empty translation')
                        if self._finish(job, 'complete', result.strip()):
                            self.health['completed'] += 1
                        break
                    except Exception:
                        if not self._current(job):
                            break
                        if attempt == self.retries:
                            self._finish(job, 'error')
                            self.health['errors'] += 1
                        else:
                            await asyncio.sleep(0.1)
                self.active_translation=None
        finally:
            self.processing = False
            self.active_translation=None

    async def run(self):
        while not self.closed:
            await self.drain()
            await asyncio.sleep(0.05)
