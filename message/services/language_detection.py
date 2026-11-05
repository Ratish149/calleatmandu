import re
from typing import Optional

DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")

STRONG_ROMANIZED_NEPALI_WORDS = frozenset(
    {
        "kati",        # how much
        "khaana",      # food
        "khana",       # food
        "mulya",       # price
        "chha",        # is (there is)
        "chhan",       # are
        "aaja",        # today
        "bholi",       # tomorrow
        "bhat",        # rice
        "tarkari",     # vegetable
        "paani",       # water
        "paisa",       # money
        "sasto",       # cheap
        "mahango",     # expensive
        "namaste",     # greeting
        "hoina",       # is not
        "hunchha",     # happens / will happen
        "hudaina",     # won't happen
        "garchha",     # does
        "chahinchha",  # is needed
        "katilai",     # how long
        "thikai",      # okay, fine
        "ramro",       # good, nice
        "mitho",       # tasty
        "kina",        # why / to buy
        "pugchha",     # is enough
        "lagchha",     # it takes / costs
        "bhaneko",     # said / meaning
        "maag",        # demand / ask
        "pailaa",      # first / before
    }
)

COMMON_ROMANIZED_NEPALI_WORDS = frozenset(
    {
        "ko",    # of / genitive
        "ka",    # of / genitive
        "ma",    # in / at
        "cha",   # is
        "ho",    # is (yes)
        "yo",    # this
        "tyo",   # that
        "chai",  # however / as for
        "pani",  # also / water
        "nai",   # exactly
        "ta",    # particle
        "ke",    # what
        "jasto", # like / similar to
        "sanga", # with
        "bata",  # from
        "lagi",  # for
        "garna", # to do
        "gareko",# done
        "dinu",  # to give
        "milcha",# fits / is allowed
        "thulo", # big
        "sano",  # small
        "khoi",  # hmm / where on earth
        "garo",  # difficult / trouble
    }
)


def _words(text: str):
    return re.findall(r"[a-z]+", text.lower())


def detect_reply_language(text) -> Optional[str]:
    """Detect the script/language of a customer message for reply-matching.

    Returns ``"devanagari"`` when the text contains Devanagari characters,
    ``"romanized"`` when it looks like romanized Nepali (Nepali written in
    Latin letters), or ``None`` when it is written in another script such as
    plain English.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    if DEVANAGARI_RANGE.search(text):
        return "devanagari"

    words = _words(text)
    if not words:
        return None

    strong = sum(1 for word in words if word in STRONG_ROMANIZED_NEPALI_WORDS)
    if strong >= 1:
        return "romanized"

    common = sum(1 for word in words if word in COMMON_ROMANIZED_NEPALI_WORDS)
    if common >= 2:
        return "romanized"

    return None