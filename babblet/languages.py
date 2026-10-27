"""Output languages advertised by the installed Hy-MT2 family model card.

Source: https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF#supported-languages
Flags are presentation markers, not a claim that languages belong to one country.
"""
_ROWS = [
 ('en','English','English','gb','ltr'), ('he','Hebrew','עברית','il','rtl'),
 ('ru','Russian','Русский','ru','ltr'), ('ar','Arabic','العربية','sa','rtl'),
 ('fr','French','Français','fr','ltr'), ('de','German','Deutsch','de','ltr'),
 ('es','Spanish','Español','es','ltr'), ('pt','Portuguese','Português','pt','ltr'),
 ('it','Italian','Italiano','it','ltr'), ('zh','Chinese','中文','cn','ltr'),
 ('zh-Hant','Traditional Chinese','繁體中文','tw','ltr'), ('ja','Japanese','日本語','jp','ltr'),
 ('ko','Korean','한국어','kr','ltr'), ('tr','Turkish','Türkçe','tr','ltr'),
 ('uk','Ukrainian','Українська','ua','ltr'), ('pl','Polish','Polski','pl','ltr'),
 ('cs','Czech','Čeština','cz','ltr'), ('nl','Dutch','Nederlands','nl','ltr'),
 ('hi','Hindi','हिन्दी','in','ltr'), ('th','Thai','ไทย','th','ltr'),
 ('vi','Vietnamese','Tiếng Việt','vn','ltr'), ('ms','Malay','Bahasa Melayu','my','ltr'),
 ('id','Indonesian','Bahasa Indonesia','id','ltr'), ('tl','Filipino','Filipino','ph','ltr'),
 ('km','Khmer','ខ្មែរ','kh','ltr'), ('my','Burmese','မြန်မာ','mm','ltr'),
 ('fa','Persian','فارسی','ir','rtl'), ('gu','Gujarati','ગુજરાતી','in','ltr'),
 ('ur','Urdu','اردو','pk','rtl'), ('te','Telugu','తెలుగు','in','ltr'),
 ('mr','Marathi','मराठी','in','ltr'), ('bn','Bengali','বাংলা','bd','ltr'),
 ('ta','Tamil','தமிழ்','lk','ltr'), ('bo','Tibetan','བོད་ཡིག','cn','ltr'),
 ('kk','Kazakh','Қазақша','kz','ltr'), ('mn','Mongolian','Монгол','mn','ltr'),
 ('ug','Uyghur','ئۇيغۇرچە','cn','rtl'), ('yue','Cantonese','廣東話','hk','ltr'),
]
CATALOG = {code:{'code':code,'name':name,'native':native,'flag':flag,'direction':direction}
           for code,name,native,flag,direction in _ROWS}


def validate_targets(targets):
    result = tuple(dict.fromkeys(targets))
    if not 1 <= len(result) <= 6 or any(code not in CATALOG for code in result):
        raise ValueError('Select between one and six supported languages')
    return result
