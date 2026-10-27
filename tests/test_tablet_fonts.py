import json
from pathlib import Path

import pytest

from babblet.languages import CATALOG

ROOT=Path(__file__).resolve().parents[1]


def test_every_advertised_language_has_glyphs_for_its_native_name():
    fonttools=pytest.importorskip('fontTools.ttLib')
    directory=ROOT/'remarkable/fonts'
    mapping=json.loads((directory/'languages.json').read_text(encoding='utf-8'))
    assert set(mapping)==set(CATALOG)
    cached={}
    for code,language in CATALOG.items():
        choice=mapping[code]
        key=(choice['file'],choice.get('face',0))
        if key not in cached:
            font=fonttools.TTFont(directory/key[0],fontNumber=key[1])
            cached[key]=set(font.getBestCmap())
            font.close()
        missing=[char for char in language['native'] if not char.isspace() and ord(char) not in cached[key]]
        assert not missing,(code,missing)
