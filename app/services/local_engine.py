import re
from collections import Counter


_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "has", "have",
    "page", "english", "study", "pack", "tofan", "lesson", "chapter", "unit", "question", "questions",
    "على", "من", "في", "إلى", "الى", "عن", "أن", "إن", "هو", "هي", "هذا", "هذه", "ذلك", "تلك",
    "و", "أو", "ثم", "كما", "لا", "ما", "مع", "بين", "يتم", "يمكن", "حيث", "عند", "الدرس", "صفحة",
}

_NOISE_RE = re.compile(r"^(?:Page|صفحة)\s*\d+$|^\d+[.)]?$", re.I)


def _meaningful_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = " ".join(raw.split()).strip()
        if not line or _NOISE_RE.fullmatch(line):
            continue
        # Ignore repeated document branding/header lines.
        normalized = re.sub(r"[^A-Za-z0-9\u0600-\u06FF ]", "", line).lower().strip()
        if normalized in {"english", "english midterm study pack tofan", "english midterm study pack"}:
            continue
        lines.append(line)
    return lines


def summarize(text: str, max_sentences: int = 8) -> str:
    """Fast local summary without an API call, with PDF noise removed."""
    lines = _meaningful_lines(text)
    source = "\n".join(lines)
    sentences = [s.strip() for s in re.split(r"(?<=[.!؟?。])\s+|\n{2,}", source) if len(s.strip()) >= 35]
    if not sentences:
        sentences = [s for s in lines if len(s) >= 35]
    if not sentences:
        return source[:3000]

    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u0600-\u06FF]{3,}", source.lower())
    freq = Counter(w for w in words if w not in _STOPWORDS)
    scored = []
    for i, sentence in enumerate(sentences):
        sw = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u0600-\u06FF]{3,}", sentence.lower())
        score = sum(freq[w] for w in sw) / max(len(sw), 1)
        if re.search(r"definition|defined|يعرف|تعريف|هو عبارة|يسمى|means|meaning", sentence, re.I):
            score += 2
        if re.search(r"\b(noun|verb|adjective|adverb|pronoun|preposition|tense|grammar|research|experience)\b", sentence, re.I):
            score += 1
        scored.append((score, i, sentence))
    chosen = sorted(scored, reverse=True)[:max_sentences]
    chosen.sort(key=lambda x: x[1])
    return "\n\n".join(s for _, _, s in chosen)[:3500]


def english_terms(text: str, limit: int = 20) -> list[str]:
    lines = _meaningful_lines(text)
    candidates = []
    for line in lines:
        # Prefer vocabulary-looking entries rather than every word in the PDF.
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]{2,}(?:\s+[A-Za-z][A-Za-z0-9_-]{2,}){0,2})\s*(?:[-–—:|]|\s{2,})", line)
        if m:
            candidates.append(m.group(1).strip())
    if not candidates:
        candidates = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,}\b", "\n".join(lines))

    cleaned = []
    seen = set()
    for term in candidates:
        key = term.lower()
        if key in _STOPWORDS or key in seen:
            continue
        if len(term) < 3 or len(term.split()) > 3:
            continue
        seen.add(key)
        cleaned.append(term)
        if len(cleaned) >= limit:
            break
    return cleaned


def local_analysis(text: str) -> dict:
    clean = "\n".join(_meaningful_lines(text))
    terms = english_terms(clean)
    return {
        "summary": summarize(clean),
        "concepts": [f"🇬🇧 {term}" for term in terms[:12]],
        "key_points": [s for s in summarize(clean, 6).split("\n\n") if s][:6],
        "definitions": [],
        "english_terms": terms,
        "source": "local",
    }


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!؟?。])\s+|\n{2,}", text) if len(s.strip()) >= 25]


def _make_mcq(sentence: str, candidates: list[str], index: int) -> dict:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u0600-\u06FF]{4,}", sentence)
    answer = next((w for w in reversed(words) if w.lower() not in _STOPWORDS), words[-1] if words else "المعلومة")
    distractors = [c for c in candidates if c.lower() != answer.lower()][:3]
    options = [answer] + distractors
    while len(options) < 3:
        options.append(f"خيار {len(options)+1}")
    shift = index % len(options)
    options = options[shift:] + options[:shift]
    return {
        "type": "mcq",
        "question": f"أي خيار وردت حوله المعلومة التالية؟\n{sentence[:500]}",
        "options": options,
        "answer": answer,
        "explanation": f"الإجابة الصحيحة هي «{answer}» لأنها واردة في محتوى الدرس.",
        "source": "local",
    }


def generate_local_questions(text: str, count: int = 10, difficulty: str = "medium") -> list[dict]:
    """Create deterministic questions locally. Gemini is not called."""
    clean = "\n".join(_meaningful_lines(text))
    sentences = _sentences(clean)
    if not sentences:
        return []
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u0600-\u06FF]{4,}", clean)
    candidates = [w for w, _ in Counter(w for w in words if w.lower() not in _STOPWORDS).most_common(20)]
    questions = []
    for i, sentence in enumerate(sentences[:count * 2]):
        if len(questions) >= count:
            break
        if i % 3 == 1:
            questions.append({
                "type": "true_false",
                "question": sentence[:650],
                "options": ["صح", "خطأ"],
                "answer": "صح",
                "explanation": "العبارة مأخوذة مباشرة من محتوى الدرس.",
                "source": "local",
            })
        else:
            questions.append(_make_mcq(sentence, candidates, i))
    return questions[:count]
