import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence, Tuple

from deep_translator import GoogleTranslator
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from tenacity import retry, wait_exponential, stop_after_attempt

from config import GlossaryTerm, TextPipelineConfig, load_text_pipeline_config


logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAMIL_UNICODE_RANGE = re.compile(r"[\u0B80-\u0BFF]")

TAMIL_INDEPENDENT_VOWELS = {
    "அ": "a",
    "ஆ": "aa",
    "இ": "i",
    "ஈ": "ee",
    "உ": "u",
    "ஊ": "oo",
    "எ": "e",
    "ஏ": "e",
    "ஐ": "ai",
    "ஒ": "o",
    "ஓ": "o",
    "ஔ": "au",
}

TAMIL_CONSONANTS = {
    "க": "k",
    "ங": "ng",
    "ச": "s",
    "ஞ": "nj",
    "ட": "d",
    "ண": "n",
    "த": "th",
    "ந": "n",
    "ப": "p",
    "ம": "m",
    "ய": "y",
    "ர": "r",
    "ல": "l",
    "வ": "v",
    "ழ": "zh",
    "ள": "l",
    "ற": "r",
    "ன": "n",
    "ஜ": "j",
    "ஷ": "sh",
    "ஸ": "s",
    "ஹ": "h",
    "ஶ": "sh",
}

TAMIL_VOWEL_SIGNS = {
    "ா": "aa",
    "ி": "i",
    "ீ": "ee",
    "ு": "u",
    "ூ": "oo",
    "ெ": "e",
    "ே": "e",
    "ை": "ai",
    "ொ": "o",
    "ோ": "o",
    "ௌ": "au",
}

TAMIL_VIRAMA = "்"


# Keep the legacy mojibake table for old fixtures, then add escaped codepoints so Tamil-script output
# can be reliably romanized for Thanglish/Tanglish targets.
LEGACY_TAMIL_INDEPENDENT_VOWELS = TAMIL_INDEPENDENT_VOWELS.copy()
LEGACY_TAMIL_CONSONANTS = TAMIL_CONSONANTS.copy()
LEGACY_TAMIL_VOWEL_SIGNS = TAMIL_VOWEL_SIGNS.copy()
LEGACY_TAMIL_VIRAMA = TAMIL_VIRAMA

TAMIL_INDEPENDENT_VOWELS = {
    "\u0B85": "a",
    "\u0B86": "aa",
    "\u0B87": "i",
    "\u0B88": "ee",
    "\u0B89": "u",
    "\u0B8A": "oo",
    "\u0B8E": "e",
    "\u0B8F": "e",
    "\u0B90": "ai",
    "\u0B92": "o",
    "\u0B93": "o",
    "\u0B94": "au",
}
TAMIL_CONSONANTS = {
    "\u0B95": "k",
    "\u0B99": "ng",
    "\u0B9A": "s",
    "\u0B9E": "nj",
    "\u0B9F": "d",
    "\u0BA3": "n",
    "\u0BA4": "th",
    "\u0BA8": "n",
    "\u0BAA": "p",
    "\u0BAE": "m",
    "\u0BAF": "y",
    "\u0BB0": "r",
    "\u0BB2": "l",
    "\u0BB5": "v",
    "\u0BB4": "zh",
    "\u0BB3": "l",
    "\u0BB1": "r",
    "\u0BA9": "n",
    "\u0B9C": "j",
    "\u0BB7": "sh",
    "\u0BB8": "s",
    "\u0BB9": "h",
    "\u0BB6": "sh",
}
TAMIL_VOWEL_SIGNS = {
    "\u0BBE": "aa",
    "\u0BBF": "i",
    "\u0BC0": "ee",
    "\u0BC1": "u",
    "\u0BC2": "oo",
    "\u0BC6": "e",
    "\u0BC7": "e",
    "\u0BC8": "ai",
    "\u0BCA": "o",
    "\u0BCB": "o",
    "\u0BCC": "au",
}
TAMIL_VIRAMA = "\u0BCD"
TAMIL_INDEPENDENT_VOWELS.update(LEGACY_TAMIL_INDEPENDENT_VOWELS)
TAMIL_CONSONANTS.update(LEGACY_TAMIL_CONSONANTS)
TAMIL_VOWEL_SIGNS.update(LEGACY_TAMIL_VOWEL_SIGNS)

LANGUAGE_PROFILES = {
    "hi": {"label": "Hindi + English", "mixed_name": "Hinglish", "script": "Devanagari", "google": "hi"},
    "ta": {"label": "Tamil + English", "mixed_name": "Tamil + English", "script": "Tamil script", "google": "ta"},
    "te": {"label": "Telugu + English", "mixed_name": "Tenglish", "script": "Telugu script", "google": "te"},
    "kn": {"label": "Kannada + English", "mixed_name": "Kanglish", "script": "Kannada script", "google": "kn"},
    "ml": {"label": "Malayalam + English", "mixed_name": "Manglish", "script": "Malayalam script", "google": "ml"},
    "bn": {"label": "Bengali + English", "mixed_name": "Benglish", "script": "Bengali script", "google": "bn"},
    "mr": {"label": "Marathi + English", "mixed_name": "Minglish", "script": "Devanagari", "google": "mr"},
    "gu": {"label": "Gujarati + English", "mixed_name": "Gujlish", "script": "Gujarati script", "google": "gu"},
    "pa": {"label": "Punjabi + English", "mixed_name": "Punglish", "script": "Gurmukhi script", "google": "pa"},
    "or": {"label": "Odia + English", "mixed_name": "Odlish", "script": "Odia script", "google": "or"},
    "as": {"label": "Assamese + English", "mixed_name": "Assamese + English", "script": "Bengali script", "google": "as"},
    "ur": {"label": "Urdu + English", "mixed_name": "Urlish", "script": "Nastaliq or Roman", "google": "ur"},
    "sa": {"label": "Sanskrit + English", "mixed_name": "Sanskrit + English", "script": "Devanagari", "google": "sa"},
    "gom": {"label": "Konkani + English", "mixed_name": "Konkani + English", "script": "Devanagari", "google": "gom"},
    "ks": {"label": "Kashmiri + English", "mixed_name": "Kashmiri + English", "script": "Nastaliq or Devanagari", "google": "ks"},
    "mai": {"label": "Maithili + English", "mixed_name": "Maithili + English", "script": "Devanagari", "google": "mai"},
    "sat": {"label": "Santali + English", "mixed_name": "Santali + English", "script": "Ol Chiki", "google": "sat"},
    "doi": {"label": "Dogri + English", "mixed_name": "Dogri + English", "script": "Devanagari", "google": "doi"},
    "brx": {"label": "Bodo + English", "mixed_name": "Bodo + English", "script": "Devanagari", "google": "brx"},
    "mni-mtei": {"label": "Manipuri + English", "mixed_name": "Manipuri + English", "script": "Meitei", "google": "mni-Mtei"},
    "sd": {"label": "Sindhi + English", "mixed_name": "Sindhi + English", "script": "Devanagari or Nastaliq", "google": "sd"},
    "tanglish": {"label": "Tanglish", "mixed_name": "Tanglish", "script": "English/Latin letters", "google": "ta", "roman": True},
}

LANGUAGE_ALIASES = {
    "hindi": "hi",
    "hinglish": "hi",
    "hindi+english": "hi",
    "hindi english": "hi",
    "tamil": "ta",
    "tamil+english": "ta",
    "tamil english": "ta",
    "tanglish": "tanglish",
    "thanglish": "tanglish",
    "roman tamil": "tanglish",
    "telugu": "te",
    "tenglish": "te",
    "telugu+english": "te",
    "telugu english": "te",
    "kannada": "kn",
    "kanglish": "kn",
    "kannada+english": "kn",
    "kannada english": "kn",
    "malayalam": "ml",
    "manglish": "ml",
    "malayalam+english": "ml",
    "malayalam english": "ml",
    "bengali": "bn",
    "benglish": "bn",
    "bengali+english": "bn",
    "bengali english": "bn",
    "marathi": "mr",
    "minglish": "mr",
    "marathi+english": "mr",
    "marathi english": "mr",
    "gujarati": "gu",
    "gujlish": "gu",
    "gujarati+english": "gu",
    "gujarati english": "gu",
    "punjabi": "pa",
    "punglish": "pa",
    "punjabi+english": "pa",
    "punjabi english": "pa",
    "odia": "or",
    "oriya": "or",
    "odlish": "or",
    "odia+english": "or",
    "oriya+english": "or",
    "odia english": "or",
    "oriya english": "or",
    "assamese": "as",
    "assamese+english": "as",
    "assamese english": "as",
    "urdu": "ur",
    "urlish": "ur",
    "urdu+english": "ur",
    "urdu english": "ur",
    "sanskrit": "sa",
    "sanskrit+english": "sa",
    "sanskrit english": "sa",
    "konkani": "gom",
    "konkani+english": "gom",
    "konkani english": "gom",
    "kashmiri": "ks",
    "kashmiri+english": "ks",
    "kashmiri english": "ks",
    "maithili": "mai",
    "maithili+english": "mai",
    "maithili english": "mai",
    "santali": "sat",
    "santali+english": "sat",
    "santali english": "sat",
    "dogri": "doi",
    "dogri+english": "doi",
    "dogri english": "doi",
    "bodo": "brx",
    "bodo+english": "brx",
    "bodo english": "brx",
    "manipuri": "mni-mtei",
    "meitei": "mni-mtei",
    "manipuri+english": "mni-mtei",
    "meitei+english": "mni-mtei",
    "manipuri english": "mni-mtei",
    "meitei english": "mni-mtei",
    "sindhi": "sd",
    "sindhi+english": "sd",
    "sindhi english": "sd",
}

INDIAN_LANGUAGE_CODES = frozenset(LANGUAGE_PROFILES)

STRICT_RULES = """\
STRICT TRANSLATION RULES:
1. Translate into {target_language} as a natural Indian language + English classroom mix.
2. Keep math, science, technical, educational, proper noun, brand, tool, and model terms in English.
3. Preserve phonetic math exactly: "D square", "e power ax", "f of D", "divided by", "equal to", "plus", "minus", variables like "m", "x", "a", "y", "c1", "c2".
4. Numbers as words stay in English: "sixteen", "thirty-two", "minus one", "five", "ten", "hundred".
5. Use natural spoken/colloquial grammar — not formal or written style.
6. Preserve paragraph breaks and line breaks from the original.
7. Use the natural connector words, particles, and verb endings of each language.
8. Do not add headers, bullets, labels, explanations, or preamble.
9. Do not translate technical/math terms into the regional language.
10. Do not use stiff formal written register; sound like a teacher talking to students.
11. For Roman transliteration requests (Tanglish, Roman Hindi, etc.) — write the Indian language words phonetically in English letters.
12. NEVER include internal reasoning, self-corrections, or meta-commentary in your output. No "Wait", "Let me redo", "I need to follow", "I should", etc. Output ONLY the final translated text.
"""

LANGUAGE_CONNECTOR_REFERENCE = {
    "ta": "Tamil connectors: of/belonging to -> -ஓட (-oda); is/are -> இருக்கு; we do -> பண்றோம்; meaning -> என்னன்னா; now -> இப்போ; let's -> போறோம்.",
    "tanglish": "Tanglish connectors: of/belonging to -> -oda; is/are -> irukku; we do -> pannrom; meaning -> ennanna; now -> ippo; let's -> porom.",
    "hi": "Hindi connectors: of/belonging to -> का/की/के; is/are -> है/हैं; we do -> करते हैं; meaning -> मतलब; now -> अब; let's -> चलते हैं.",
    "te": "Telugu connectors: of/belonging to -> యొక్క; is/are -> ఉంది/ఉన్నాయి; we do -> చేస్తాము; now -> ఇప్పుడు; meaning -> అంటే.",
    "kn": "Kannada connectors: of/belonging to -> ಯ; is/are -> ಇದೆ/ಇವೆ; we do -> ಮಾಡ್ತೀವಿ; now -> ಈಗ; meaning -> ಅಂದ್ರೆ.",
    "ml": "Malayalam connectors: of/belonging to -> ന്റെ; is/are -> ആണ്; we do -> ചെയ്യുന്നു; now -> ഇപ്പോൾ; meaning -> എന്നാൽ.",
    "bn": "Bengali connectors: of/belonging to -> এর; is/are -> আছে/হয়; we do -> করি; now -> এখন; meaning -> মানে.",
    "mr": "Marathi connectors: of/belonging to -> चा/ची/चे; is/are -> आहे/आहेत; now -> आता; meaning -> म्हणजे.",
    "gu": "Gujarati connectors: of/belonging to -> નો/ની/નું; is/are -> છે; now -> હવે; meaning -> એટલે.",
    "pa": "Punjabi connectors: of/belonging to -> ਦਾ/ਦੀ/ਦੇ; is/are -> ਹੈ/ਹਨ; now -> ਹੁਣ; meaning -> ਮਤਲਬ.",
}

CODE_SWITCHING_BASE = (
    "Apply the language-translator workflow: identify the target mixed language, "
    "translate sentence by sentence, preserve line breaks, and output only the translated text. "
    "Use natural code-mixing as used in classrooms, YouTube lessons, chat apps, and everyday conversation across India. "
    "Keep common English verbs and short phrases students naturally use in class. "
    "Use target-language connector words, particles, and verb endings. "
    "Ensure the mixed-language output flows naturally when spoken aloud and roughly fits dubbing timing. "
    "Do not add preamble like 'Here is the Hinglish version:' — output translation directly."
)

AUTO_PRESERVE_TERMS = (
    "characteristic equation",
    "auxiliary equation",
    "differential equation",
    "square matrix",
    "matrix",
    "determinant",
    "leading diagonal elements",
    "diagonal elements",
    "constant coefficients",
    "cross multiply",
    "substitute",
    "formula",
    "equation",
    "variable",
    "integration",
    "derivative",
    "coefficient",
    "coefficients",
    "lambda square",
    "lambda",
    "alpha",
    "beta",
    "gamma",
    "theta",
    "root",
    "roots",
    "plus",
    "minus",
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "equal to",
    "not equal to",
    "is equal to",
    "divided by",
    "multiplied by",
    "D square",
    "e power ax",
    "f of D",
)

AUTO_PRESERVE_VARIABLE_RE = re.compile(
    r"\b(?:a\d+|c\d+|[A-Z]|[xyzmnabcd])\b",
    re.IGNORECASE,
)

TRANSLATION_MODE_GUIDANCE = {
    "academic_exact": "Keep the translation precise, faithful, and academically correct.",
    "student_friendly": "Keep the translation natural, clear, and easy for students to follow.",
    "teacher_explanatory": "Keep the translation instructional and slightly explanatory without becoming verbose.",
    "subtitle_compact": "Keep the translation concise and subtitle-friendly while preserving meaning.",
}


def _log_stage(stage: str, status: str, **details: object) -> None:
    payload = {"stage": stage, "status": status}
    payload.update(details)
    logger.info(json.dumps(payload, ensure_ascii=False))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


_LLM_LEAK_PATTERNS = re.compile(
    r"^(?:Wait[\s,\-—–]|Let me redo|I (?:need|should|must|have) to |"
    r"I'll |Hmm|Note:|Correction:|Actually,|Sorry|Apolog|"
    r"Let me (?:follow|try|fix|correct|rewrite|translate|use)|"
    r"Here (?:is|are) the |The (?:translation|output|result) (?:is|should)|"
    r"strict rule)",
    re.IGNORECASE,
)


def _strip_llm_reasoning(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue
        if _LLM_LEAK_PATTERNS.search(stripped):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    return result if result else text


def _normalize_translation_output(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in (text or "").splitlines()]
    normalized = "\n".join(line for line in lines if line).strip()
    return _strip_llm_reasoning(normalized)


def normalize_target_language(target_language: str) -> str:
    normalized = _normalize_text(target_language).lower().replace("_", " ")
    if normalized in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[normalized]
    if normalized in LANGUAGE_PROFILES:
        return normalized
    return normalized


def _get_language_profile(target_language: str) -> Optional[dict]:
    return LANGUAGE_PROFILES.get(normalize_target_language(target_language))


def _is_tanglish_target(target_language: str) -> bool:
    profile = _get_language_profile(target_language)
    return bool(profile and profile.get("roman"))


def _is_indian_language(target_language: str) -> bool:
    return normalize_target_language(target_language) in INDIAN_LANGUAGE_CODES


def _build_strict_rules(target_language: str) -> str:
    if not (
        _is_indian_language(target_language) or _is_tanglish_target(target_language)
    ):
        return ""
    return STRICT_RULES.format(target_language=_describe_target_language(target_language))


def _describe_target_language(target_language: str) -> str:
    profile = _get_language_profile(target_language)
    if profile and profile.get("roman"):
        return (
            f"{profile['mixed_name']} (Tamil written using English/Latin letters only; never use Tamil script. "
            "Keep common English technical words in English when natural.)"
        )
    if profile:
        return (
            f"{profile['label']} / {profile['mixed_name']} in {profile['script']} "
            "(use the native script for connective tissue; keep English for all technical, scientific, mathematical, "
            "proper noun, brand, tool, and model terms)"
        )
    return target_language


def _build_target_style_guidance(target_language: str, stage: str) -> str:
    profile = _get_language_profile(target_language)
    normalized_language = normalize_target_language(target_language)
    connector_reference = LANGUAGE_CONNECTOR_REFERENCE.get(normalized_language, "")
    if _is_tanglish_target(target_language):
        base_guidance = (
            "Use a classroom-style Tanglish voice for Indian educational content. "
            "Sound like a friendly teacher explaining concepts to students. "
            "Write spoken Tamil naturally in English/Latin letters only. "
            "Keep familiar academic and technical words in English when students would naturally hear them that way in class. "
            "Use natural Roman Tamil connector words and verb endings. "
            "Do not add headers, labels, bullets, explanations, or preamble. "
            "Avoid Tamil script, stiff literary Tamil, overly literal wording, and heavy slang. "
            f"{connector_reference} {CODE_SWITCHING_BASE}"
        )
        if stage == "review":
            return f"{base_guidance} Repair awkward romanization and make the line feel natural when read aloud in class."
        if stage == "subtitle":
            return f"{base_guidance} Keep each subtitle short, easy to scan in SRT format, and natural for dubbing."
        return base_guidance

    if _is_indian_language(target_language):
        mixed_name = profile["mixed_name"] if profile else "Indian language + English"
        base_guidance = (
            f"Use a classroom-style {mixed_name} voice for Indian educational content. "
            "Sound like a friendly teacher explaining concepts to students. "
            "Write connective tissue (conjunctions, prepositions, discourse markers) in the target language native script. "
            "Preserve all technical, scientific, mathematical, and educational terms exactly in English. "
            "Preserve paragraph breaks and line breaks. Do not add labels, headers, bullets, or preamble. "
            "Avoid overly literal translation, stiff formal language, and heavy slang. "
            f"{connector_reference} {CODE_SWITCHING_BASE}"
        )
        if stage == "review":
            return (
                f"{base_guidance} "
                "Repair unnatural phrasing and ensure English technical terms are preserved unchanged."
            )
        if stage == "subtitle":
            return (
                f"{base_guidance} "
                "Keep each subtitle short, easy to scan in SRT format, and natural for dubbing."
            )
        return base_guidance

    return ""


def _transliterate_tamil_to_tanglish(text: str) -> str:
    if not text:
        return ""

    result: List[str] = []
    index = 0

    while index < len(text):
        char = text[index]

        if char in TAMIL_INDEPENDENT_VOWELS:
            result.append(TAMIL_INDEPENDENT_VOWELS[char])
            index += 1
            continue

        if char in TAMIL_CONSONANTS:
            base = TAMIL_CONSONANTS[char]
            next_char = text[index + 1] if index + 1 < len(text) else ""

            if next_char in {TAMIL_VIRAMA, LEGACY_TAMIL_VIRAMA}:
                result.append(base)
                index += 2
                continue

            if next_char in TAMIL_VOWEL_SIGNS:
                result.append(base + TAMIL_VOWEL_SIGNS[next_char])
                index += 2
                continue

            result.append(base + "a")
            index += 1
            continue

        if char in TAMIL_VOWEL_SIGNS:
            result.append(TAMIL_VOWEL_SIGNS[char])
            index += 1
            continue

        if char == "\u0B83":
            result.append("h")
            index += 1
            continue

        if char == "ஃ":
            result.append("h")
            index += 1
            continue

        result.append(char)
        index += 1

    return "".join(result)


def adapt_text_for_target_language(text: str, target_language: str) -> str:
    normalized_text = _normalize_translation_output(text)
    if _is_tanglish_target(target_language) and TAMIL_UNICODE_RANGE.search(
        normalized_text
    ):
        return _normalize_translation_output(_transliterate_tamil_to_tanglish(normalized_text))
    return normalized_text


def _build_glossary_prompt(glossary_terms: Sequence[GlossaryTerm]) -> str:
    if not glossary_terms:
        return "Glossary protection: none."

    entries = []
    for term in glossary_terms:
        if term.target:
            entries.append(f"{term.source} -> {term.target}")
        else:
            entries.append(f"{term.source} -> keep unchanged")
    return "Glossary protection:\n" + "\n".join(entries)


def _protect_text(
    text: str,
    glossary_terms: Sequence[GlossaryTerm],
    prefer_target: bool,
) -> Tuple[str, Dict[str, str]]:
    protected_text = text or ""
    replacements: Dict[str, str] = {}

    sorted_terms = sorted(
        glossary_terms, key=lambda item: len(item.source), reverse=True
    )
    for index, term in enumerate(sorted_terms):
        variants = [term.source]
        if term.target and term.target not in variants:
            variants.append(term.target)

        for variant in sorted(set(filter(None, variants)), key=len, reverse=True):
            placeholder = f"GLTERM{index}_{len(replacements)}TOKEN"
            replacement_value = (
                term.target if prefer_target and term.target else term.source
            )
            if variant not in protected_text:
                continue
            protected_text = protected_text.replace(variant, placeholder)
            replacements[placeholder] = replacement_value

    protected_text = _protect_auto_preserved_terms(protected_text, replacements)
    return protected_text, replacements


def _protect_auto_preserved_terms(text: str, replacements: Dict[str, str]) -> str:
    protected_text = text or ""

    for term in sorted(AUTO_PRESERVE_TERMS, key=len, reverse=True):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", re.IGNORECASE)

        def replace_term(match: re.Match) -> str:
            placeholder = f"AUTOTERM{len(replacements)}TOKEN"
            replacements[placeholder] = match.group(0)
            return placeholder

        protected_text = pattern.sub(replace_term, protected_text)

    def replace_variable(match: re.Match) -> str:
        placeholder = f"AUTOTERM{len(replacements)}TOKEN"
        replacements[placeholder] = match.group(0)
        return placeholder

    return AUTO_PRESERVE_VARIABLE_RE.sub(replace_variable, protected_text)


def _restore_text(text: str, replacements: Dict[str, str]) -> str:
    restored_text = text or ""
    for placeholder, replacement in replacements.items():
        restored_text = restored_text.replace(placeholder, replacement)
    return _normalize_translation_output(restored_text)


def _literal_translate_text(text: str, target_language: str = "hi") -> str:
    if not text or not text.strip():
        return ""

    try:
        profile = _get_language_profile(target_language)
        lang_code = profile["google"] if profile else normalize_target_language(target_language)
        translator = GoogleTranslator(source="auto", target=lang_code)
        translated_text = translator.translate(text)
        if not translated_text or not translated_text.strip():
            raise RuntimeError("Google Translate returned an empty result.")
        return adapt_text_for_target_language(translated_text, target_language)
    except Exception as exc:
        logger.warning("Translation API failed: %s", exc)
        raise


class TextProcessingProvider(ABC):
    provider_name = "base"

    @abstractmethod
    async def cleanup_text(
        self, text: str, glossary_terms: Sequence[GlossaryTerm]
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def translate_text(
        self,
        text: str,
        target_language: str,
        translation_mode: str,
        glossary_terms: Sequence[GlossaryTerm],
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def review_translation(
        self,
        source_text: str,
        translated_text: str,
        target_language: str,
        translation_mode: str,
        glossary_terms: Sequence[GlossaryTerm],
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def compress_subtitle(
        self,
        text: str,
        target_language: str,
        glossary_terms: Sequence[GlossaryTerm],
        max_subtitle_chars: int,
        max_subtitle_words: int,
    ) -> str:
        raise NotImplementedError


class OpenAITextProcessingProvider(TextProcessingProvider):
    provider_name = "openai"

    def __init__(self, api_key: Optional[str]) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI text provider.")
        self.chat = ChatOpenAI(
            temperature=0.2,
            openai_api_key=api_key,
            max_retries=0,
            request_timeout=30,
        )

    async def cleanup_text(
        self, text: str, glossary_terms: Sequence[GlossaryTerm]
    ) -> str:
        system_prompt = (
            "You clean up raw speech-to-text transcript segments. "
            "Improve punctuation, casing, and obvious sentence boundaries. "
            "Remove filler noise only when safe. Preserve meaning, formulas, numbers, code, technical keywords, "
            "and glossary-protected terms. Return only the cleaned segment text."
        )
        return await self._complete(
            system_prompt,
            f"{_build_glossary_prompt(glossary_terms)}\n\nSegment:\n{text}",
        )

    async def translate_text(
        self,
        text: str,
        target_language: str,
        translation_mode: str,
        glossary_terms: Sequence[GlossaryTerm],
    ) -> str:
        mode_guidance = TRANSLATION_MODE_GUIDANCE.get(
            translation_mode,
            TRANSLATION_MODE_GUIDANCE["student_friendly"],
        )
        strict_rules = _build_strict_rules(target_language)
        system_prompt = (
            "You are an expert translator for video localization. "
            f"Translate into {_describe_target_language(target_language)}. {mode_guidance} "
            f"{_build_target_style_guidance(target_language, 'translation')} "
            f"{strict_rules}"
            "Keep the output suitable for subtitles and TTS. Return ONLY the final translated text. "
            "Never include reasoning, self-corrections, or meta-commentary like 'Wait', 'Let me redo', 'I need to follow the strict rule', etc."
        )
        translated_text = await self._complete(
            system_prompt,
            f"{_build_glossary_prompt(glossary_terms)}\n\nSource:\n{text}",
        )
        return adapt_text_for_target_language(translated_text, target_language)

    async def review_translation(
        self,
        source_text: str,
        translated_text: str,
        target_language: str,
        translation_mode: str,
        glossary_terms: Sequence[GlossaryTerm],
    ) -> str:
        mode_guidance = TRANSLATION_MODE_GUIDANCE.get(
            translation_mode,
            TRANSLATION_MODE_GUIDANCE["student_friendly"],
        )
        strict_rules = _build_strict_rules(target_language)
        system_prompt = (
            "You are reviewing a translation for dubbing and subtitles. "
            "Compare the source and translated text. Repair missing meaning, over-translation, terminology drift, "
            f"and unnatural phrasing. {mode_guidance} {_build_target_style_guidance(target_language, 'review')} "
            f"{strict_rules}"
            "Keep it concise and TTS-friendly. "
            "Return ONLY the repaired translation. No reasoning, no self-corrections, no meta-commentary."
        )
        user_prompt = (
            f"{_build_glossary_prompt(glossary_terms)}\n\n"
            f"Target language: {_describe_target_language(target_language)}\n"
            f"Source:\n{source_text}\n\n"
            f"Current translation:\n{translated_text}"
        )
        reviewed_text = await self._complete(system_prompt, user_prompt)
        return adapt_text_for_target_language(reviewed_text, target_language)

    async def compress_subtitle(
        self,
        text: str,
        target_language: str,
        glossary_terms: Sequence[GlossaryTerm],
        max_subtitle_chars: int,
        max_subtitle_words: int,
    ) -> str:
        strict_rules = _build_strict_rules(target_language)
        system_prompt = (
            "You rewrite subtitle lines for readability and dubbing. "
            "Shorten when needed while preserving meaning and protected academic terms. "
            f"{_build_target_style_guidance(target_language, 'subtitle')} "
            f"{strict_rules}"
            "Do not add information. Return only one compact subtitle segment."
        )
        user_prompt = (
            f"{_build_glossary_prompt(glossary_terms)}\n\n"
            f"Target language: {_describe_target_language(target_language)}\n"
            f"Target max characters: {max_subtitle_chars}\n"
            f"Target max words: {max_subtitle_words}\n\n"
            f"Subtitle text:\n{text}"
        )
        compressed_text = await self._complete(system_prompt, user_prompt)
        return adapt_text_for_target_language(compressed_text, target_language)

    @retry(wait=wait_exponential(multiplier=2, min=3, max=30), stop=stop_after_attempt(4))
    async def _complete(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.chat.agenerate(
            [[SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]]
        )
        return _normalize_translation_output(response.generations[0][0].text)


class AnthropicTextProcessingProvider(TextProcessingProvider):
    provider_name = "anthropic"

    def __init__(self, api_key: Optional[str]) -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic text provider.")
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise ValueError(
                "The 'anthropic' package is required for the Anthropic text provider. "
                "Install backend requirements first."
            ) from exc

        self.client = AsyncAnthropic(api_key=api_key, max_retries=3)
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        try:
            self.max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "2048"))
        except ValueError:
            self.max_tokens = 2048

    async def cleanup_text(
        self, text: str, glossary_terms: Sequence[GlossaryTerm]
    ) -> str:
        system_prompt = (
            "You clean up raw speech-to-text transcript segments. "
            "Improve punctuation, casing, and obvious sentence boundaries. "
            "Remove filler noise only when safe. Preserve meaning, formulas, numbers, code, technical keywords, "
            "and glossary-protected terms. Return only the cleaned segment text."
        )
        return await self._complete(
            system_prompt,
            f"{_build_glossary_prompt(glossary_terms)}\n\nSegment:\n{text}",
        )

    async def translate_text(
        self,
        text: str,
        target_language: str,
        translation_mode: str,
        glossary_terms: Sequence[GlossaryTerm],
    ) -> str:
        mode_guidance = TRANSLATION_MODE_GUIDANCE.get(
            translation_mode,
            TRANSLATION_MODE_GUIDANCE["student_friendly"],
        )
        strict_rules = _build_strict_rules(target_language)
        system_prompt = (
            "You are an expert translator for video localization. "
            f"Translate into {_describe_target_language(target_language)}. {mode_guidance} "
            f"{_build_target_style_guidance(target_language, 'translation')} "
            f"{strict_rules}"
            "Keep the output suitable for subtitles and TTS. Return ONLY the final translated text. "
            "Never include reasoning, self-corrections, or meta-commentary like 'Wait', 'Let me redo', 'I need to follow the strict rule', etc."
        )
        translated_text = await self._complete(
            system_prompt,
            f"{_build_glossary_prompt(glossary_terms)}\n\nSource:\n{text}",
        )
        return adapt_text_for_target_language(translated_text, target_language)

    async def review_translation(
        self,
        source_text: str,
        translated_text: str,
        target_language: str,
        translation_mode: str,
        glossary_terms: Sequence[GlossaryTerm],
    ) -> str:
        mode_guidance = TRANSLATION_MODE_GUIDANCE.get(
            translation_mode,
            TRANSLATION_MODE_GUIDANCE["student_friendly"],
        )
        strict_rules = _build_strict_rules(target_language)
        system_prompt = (
            "You are reviewing a translation for dubbing and subtitles. "
            "Compare the source and translated text. Repair missing meaning, over-translation, terminology drift, "
            f"and unnatural phrasing. {mode_guidance} {_build_target_style_guidance(target_language, 'review')} "
            f"{strict_rules}"
            "Keep it concise and TTS-friendly. "
            "Return ONLY the repaired translation. No reasoning, no self-corrections, no meta-commentary."
        )
        user_prompt = (
            f"{_build_glossary_prompt(glossary_terms)}\n\n"
            f"Target language: {_describe_target_language(target_language)}\n"
            f"Source:\n{source_text}\n\n"
            f"Current translation:\n{translated_text}"
        )
        reviewed_text = await self._complete(system_prompt, user_prompt)
        return adapt_text_for_target_language(reviewed_text, target_language)

    async def compress_subtitle(
        self,
        text: str,
        target_language: str,
        glossary_terms: Sequence[GlossaryTerm],
        max_subtitle_chars: int,
        max_subtitle_words: int,
    ) -> str:
        strict_rules = _build_strict_rules(target_language)
        system_prompt = (
            "You rewrite subtitle lines for readability and dubbing. "
            "Shorten when needed while preserving meaning and protected academic terms. "
            f"{_build_target_style_guidance(target_language, 'subtitle')} "
            f"{strict_rules}"
            "Do not add information. Return only one compact subtitle segment."
        )
        user_prompt = (
            f"{_build_glossary_prompt(glossary_terms)}\n\n"
            f"Target language: {_describe_target_language(target_language)}\n"
            f"Target max characters: {max_subtitle_chars}\n"
            f"Target max words: {max_subtitle_words}\n\n"
            f"Subtitle text:\n{text}"
        )
        compressed_text = await self._complete(system_prompt, user_prompt)
        return adapt_text_for_target_language(compressed_text, target_language)

    @retry(wait=wait_exponential(multiplier=2, min=3, max=30), stop=stop_after_attempt(4))
    async def _complete(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text_parts = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ]
        return _normalize_translation_output("\n".join(text_parts))


class GoogleTranslateProvider(TextProcessingProvider):
    provider_name = "google"

    async def cleanup_text(
        self, text: str, glossary_terms: Sequence[GlossaryTerm]
    ) -> str:
        return _normalize_text(text)

    async def translate_text(
        self,
        text: str,
        target_language: str,
        translation_mode: str,
        glossary_terms: Sequence[GlossaryTerm],
    ) -> str:
        return adapt_text_for_target_language(
            _literal_translate_text(text, target_language), target_language
        )

    async def review_translation(
        self,
        source_text: str,
        translated_text: str,
        target_language: str,
        translation_mode: str,
        glossary_terms: Sequence[GlossaryTerm],
    ) -> str:
        return adapt_text_for_target_language(translated_text, target_language)

    async def compress_subtitle(
        self,
        text: str,
        target_language: str,
        glossary_terms: Sequence[GlossaryTerm],
        max_subtitle_chars: int,
        max_subtitle_words: int,
    ) -> str:
        return adapt_text_for_target_language(text, target_language)


def create_text_processing_provider(provider_name: str) -> TextProcessingProvider:
    normalized_name = (provider_name or "").strip().lower()

    if normalized_name == "openai":
        return OpenAITextProcessingProvider(OPENAI_API_KEY)
    if normalized_name in {"anthropic", "claude"}:
        return AnthropicTextProcessingProvider(os.getenv("ANTHROPIC_API_KEY"))
    if normalized_name == "google":
        return GoogleTranslateProvider()

    raise ValueError(f"Unsupported text processing provider: {provider_name}")


async def translate_text_llm(
    text: str, target_language: str, translation_mode: str = "student_friendly"
) -> str:
    provider = create_text_processing_provider("openai")
    translated_text = await provider.translate_text(
        text, target_language, translation_mode, []
    )
    return adapt_text_for_target_language(translated_text, target_language)


def translate_text_literal(text: str, target_language: str = "hi") -> str:
    return adapt_text_for_target_language(
        _literal_translate_text(text, target_language), target_language
    )


async def _translate_segment(
    provider: TextProcessingProvider,
    fallback_provider: Optional[TextProcessingProvider],
    segment: dict,
    target_language: str,
    config: TextPipelineConfig,
) -> dict:
    text, replacements = _protect_text(
        segment.get("text", ""), config.glossary_terms, prefer_target=True
    )

    try:
        translated_text = await provider.translate_text(
            text,
            target_language,
            config.translation_mode,
            config.glossary_terms,
        )
    except Exception as exc:
        if fallback_provider:
            _log_stage(
                "translation",
                "fallback_used",
                provider=provider.provider_name,
                fallback_provider=fallback_provider.provider_name,
                reason=str(exc),
            )
            logger.warning(f"Translation provider '{provider.provider_name}' failed: {exc}. Falling back to '{fallback_provider.provider_name}'.")
            translated_text = await fallback_provider.translate_text(
                text,
                target_language,
                config.translation_mode,
                config.glossary_terms,
            )
        else:
            raise

    final_text = adapt_text_for_target_language(
        _restore_text(translated_text, replacements),
        target_language,
    )
    if not final_text or not final_text.strip():
        logger.warning(
            "Empty translation for segment %.1f-%.1f, using original text",
            segment.get("start", 0), segment.get("end", 0),
        )
        final_text = segment.get("text", "")

    return {
        "start": segment["start"],
        "end": segment["end"],
        "text": final_text,
    }


async def translate_segments(
    segments: List[dict],
    target_language: str = "hi",
    config: Optional[TextPipelineConfig] = None,
) -> List[dict]:
    config = config or load_text_pipeline_config()
    provider = create_text_processing_provider(config.primary_llm_provider)

    fallback_provider: Optional[TextProcessingProvider] = None
    if (
        config.fallback_llm_provider
        and config.fallback_llm_provider != config.primary_llm_provider
    ):
        try:
            fallback_provider = create_text_processing_provider(
                config.fallback_llm_provider
            )
        except Exception as exc:
            logger.warning(
                "Unable to initialize fallback translation provider: %s", exc
            )

    translated_segments = []
    _log_stage(
        "translation",
        "started",
        provider=provider.provider_name,
        segments=len(segments),
    )

    for segment in segments:
        translated_segments.append(
            await _translate_segment(
                provider, fallback_provider, segment, target_language, config
            )
        )

    _log_stage(
        "translation",
        "completed",
        provider=provider.provider_name,
        segments=len(translated_segments),
    )
    return translated_segments
