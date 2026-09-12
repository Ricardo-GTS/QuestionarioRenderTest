import enum


class QuestionStatus(str, enum.Enum):
    ACTIVE = "active"
    REPORTED = "reported"
    REMOVED = "removed"
