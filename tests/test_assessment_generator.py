from app.agents.assessment_generator import GeneratedQuestion, grade_answers


def test_grade_answers_returns_score_and_per_question_analysis():
    questions = [
        GeneratedQuestion(1, "mcq", "2+2?", ["3", "4", "5", "6"], "4", "Arithmetic.", 1),
        GeneratedQuestion(2, "true_false", "Python is a language.", ["صح", "خطأ"], "صح", "Fact.", 2),
    ]
    score, maximum, details = grade_answers(questions, {"1": "4", "2": "خطأ"})
    assert score == 1
    assert maximum == 3
    assert details["1"]["correct"] is True
    assert details["2"]["correct"] is False
    assert details["2"]["correct_answer"] == "صح"
