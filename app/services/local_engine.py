import re
from collections import Counter


_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "has", "have",
    "page", "english", "study", "pack", "tofan", "lesson", "chapter", "unit", "question", "questions",
    "شرح", "مبسط", "أمثلة", "مثال", "اختبارات", "شاملة", "مطابقة", "الميدتيرم", "اسم", "التاريخ",
    "على", "من", "في", "إلى", "الى", "عن", "أن", "إن", "هو", "هي", "هذا", "هذه", "ذلك", "تلك",
    "و", "أو", "ثم", "كما", "لا", "ما", "مع", "بين", "يتم", "يمكن", "حيث", "عند", "الدرس", "صفحة",
}

_NOISE_RE = re.compile(
    r"^(?:Page|صفحة)\s*\d+$|^\d+[.)]?$|^(?:name|date|اسم|التاريخ)\s*:?[\s_]*$",
    re.I,
)


def _normalize_line(line: str) -> str:
    return " ".join(line.replace("\u200b", " ").replace("\ufeff", " ").split()).strip()


def _is_noise(line: str) -> bool:
    line = _normalize_line(line)
    if not line or _NOISE_RE.fullmatch(line):
        return True
    compact = re.sub(r"[^A-Za-z0-9\u0600-\u06FF ]", "", line).lower().strip()
    if compact in {"english", "english midterm study pack tofan", "english midterm study pack"}:
        return True
    # Common cover/template phrases should not become the page explanation.
    if re.search(r"شرح\s+مبسط.*5\s+اختبارات|5\s+اختبارات.*الميدتيرم", line, re.I):
        return True
    return False


def _meaningful_lines(text: str) -> list[str]:
    lines = []
    seen = Counter()
    raw_lines = []
    for raw in text.replace("\r", "\n").splitlines():
        line = _normalize_line(raw)
        if _is_noise(line):
            continue
        raw_lines.append(line)
        seen[line.casefold()] += 1

    # Repeated PDF headers/footers are a major source of the old corrupted-looking
    # explanations. Keep one copy only, while preserving legitimate repeated content
    # such as numbered examples.
    for line in raw_lines:
        if seen[line.casefold()] > 1 and len(line) < 180:
            if any(line.casefold() == x.casefold() for x in lines):
                continue
        normalized = re.sub(r"[^A-Za-z0-9\u0600-\u06FF ]", "", line).lower().strip()
        if normalized in {"english", "english midterm study pack tofan", "english midterm study pack"}:
            continue
        lines.append(line)
    return lines


def _sentences_from_lines(lines: list[str]) -> list[str]:
    source = "\n".join(lines)
    parts = re.split(r"(?<=[.!؟?。])\s+|\n{2,}", source)
    result = []
    seen = set()
    for part in parts:
        sentence = _normalize_line(part)
        if len(sentence) < 25 or _is_noise(sentence):
            continue
        key = sentence.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(sentence)
    return result


def summarize(text: str, max_sentences: int = 6) -> str:
    lines = _meaningful_lines(text)
    if not lines:
        return "لم أجد محتوى واضحًا في هذه الصفحة."
    source = "\n".join(lines)
    sentences = _sentences_from_lines(lines)
    if not sentences:
        return "\n".join(lines[:max_sentences])[:2600]

    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u0600-\u06FF]{3,}", source.lower())
    freq = Counter(w for w in words if w not in _STOPWORDS)
    scored = []
    for i, sentence in enumerate(sentences):
        sw = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u0600-\u06FF]{3,}", sentence.lower())
        score = sum(freq[w] for w in sw) / max(len(sw), 1)
        if re.search(r"definition|defined|يعرف|تعريف|هو عبارة|يسمى|means|meaning", sentence, re.I):
            score += 3
        if re.search(r"important|key|مهم|أساسي|رئيسي|يشمل|يتكون|يعتمد", sentence, re.I):
            score += 1.5
        scored.append((score, i, sentence))
    chosen = sorted(scored, key=lambda item: (-item[0], item[1]))[:max_sentences]
    chosen.sort(key=lambda item: item[1])
    return "\n\n".join(s for _, _, s in chosen)[:3000]


def english_terms(text: str, limit: int = 12) -> list[str]:
    lines = _meaningful_lines(text)
    candidates = []
    for line in lines:
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
    summary = summarize(clean)
    key_points = _sentences_from_lines(_meaningful_lines(clean))[:6]
    return {
        "summary": summary,
        "concepts": [f"🇬🇧 {term}" for term in terms],
        "key_points": key_points,
        "definitions": [],
        "english_terms": terms,
        "source": "local",
    }


def _full_explanation(sentence: str, answer: str, question_type: str = "mcq") -> str:
    if question_type == "true_false":
        return (
            f"📖 <b>الشرح الكامل:</b> هذه العبارة مبنية على المعلومة التالية من الدرس:\n"
            f"«{sentence[:1200]}»\n\n"
            f"✅ <b>الإجابة الصحيحة:</b> {answer}\n"
            "💡 <b>الفكرة:</b> احفظ المعلومة كما وردت في الدرس، لأنها الأساس الذي بُني عليه السؤال."
        )
    return (
        f"📖 <b>الشرح الكامل:</b> الإجابة الصحيحة هي «{answer}» لأن الدرس يربطها مباشرة بهذه المعلومة:\n"
        f"«{sentence[:1200]}»\n\n"
        f"✅ <b>الإجابة:</b> {answer}\n"
        "💡 <b>الفكرة:</b> ركّز على العلاقة بين السؤال والمعلومة الأصلية بدل حفظ الخيار وحده."
    )


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
        "question": f"أي خيار يرتبط بالمعلومة التالية؟\n{sentence[:500]}",
        "options": options,
        "answer": answer,
        "explanation": _full_explanation(sentence, answer, "mcq"),
        "source": "local",
    }


def generate_local_questions(text: str, count: int = 10, difficulty: str = "medium") -> list[dict]:
    clean = "\n".join(_meaningful_lines(text))
    sentences = _sentences_from_lines(_meaningful_lines(clean))
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
                "explanation": _full_explanation(sentence, "صح", "true_false"),
                "source": "local",
            })
        else:
            questions.append(_make_mcq(sentence, candidates, i))
    return questions[:count]
