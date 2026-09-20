from app.files.extractor import FileExtractionError, extract_teaching_text


def test_extract_txt():
    text, pages = extract_teaching_text("lesson.txt", b"Hello TOFAN")
    assert text == "Hello TOFAN"
    assert pages == 1


def test_reject_unsupported_file():
    try:
        extract_teaching_text("lesson.exe", b"bad")
        assert False, "unsupported file must be rejected"
    except FileExtractionError:
        pass
