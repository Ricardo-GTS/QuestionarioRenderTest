from app.core.security import is_admin_email


def test_is_admin_email_true_for_configured_email():
    assert is_admin_email("admin@example.com") is True


def test_is_admin_email_case_insensitive():
    assert is_admin_email("ADMIN@EXAMPLE.COM") is True


def test_is_admin_email_false_for_other_email():
    assert is_admin_email("aluno@example.com") is False
