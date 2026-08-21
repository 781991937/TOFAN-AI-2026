from app.database import Database


def test_database_lifecycle(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.ensure_user(123, "Student")
    user = db.get_user(123)
    assert user["first_name"] == "Student"
    lesson_id = db.create_lesson(123, "lesson.txt", "txt", "data/uploads/lesson.txt", "content")
    assert db.get_lesson(lesson_id, 123)["file_name"] == "lesson.txt"
    quiz_id = db.create_quiz(lesson_id, '[{"question":"2+2","answer":"4"}]')
    result_id = db.save_result(123, quiz_id, 1, 1, 100.0, '["4"]')
    assert result_id > 0
    assert db.get_stats(123)["average"] == 100.0
