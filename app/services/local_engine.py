import re
from collections import Counter


_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "has", "have",
    "على", "من", "في", "إلى", "الى", "عن", "أن", "إن", "هو", "هي", "هذا", "هذه", "ذلك", "تلك",
    "و", "أو", "ثم", "كما", "لا", "ما", "من", "مع", "بين", "يتم", "يمكن", "حيث", "عند",
}


def summarize(text: str, max_sentences: int = 8) -> str:
    """Fast local summary: selects informative sentences without any API call."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!؟?。])\s+|\n{2,}", text) if len(s.strip()) >= 35]
    if not sentences:
        return text[:3000]
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u0600-\u06FF]{3,}", text.lower())
    freq = Counter(w for w in words if w not in _STOPWORDS)
    scored = []
    for i, sentence in enumerate(sentences):
        sw = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u0600-\u06FF]{3,}", sentence.lower())
        score = sum(freq[w] for w in sw) / max(len(sw), 1)
        if re.search(r"definition|defined|يعرف|تعريف|هو عبارة|يسمى|means|meaning", sentence, re.I):
            score += 2
        scored.append((score, i, sentence))
    chosen = sorted(scored, reverse=True)[:max_sentences]
    chosen.sort(key=lambda x: x[1])
    return "\n\n".join(s for _, _, s in chosen)[:3500]


def english_terms(text: str, limit: int = 20) -> list[str]:
    terms = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{2,}(?:\s+[A-Za-z][A-Za-z0-9_-]{2,}){0,2}\b", text)
    counts = Counter(t.strip() for t in terms if t.lower() not in _STOPWORDS)
    return [term for term, _ in counts.most_common(limit)]


def local_analysis(text: str) -> dict:
    terms = english_terms(text)
    return {
        "summary": summarize(text),
        "concepts": [f"🇬🇧 {term}" for term in terms[:12]],
        "key_points": [s for s in summarize(text, 6).split("\n\n") if s][:6],
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
    # deterministic rotation so repeated quizzes are stable and cacheable
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
    sentences = _sentences(text)
    if not sentences:
        return []
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u0600-\u06FF]{4,}", text)
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
