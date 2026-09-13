import enum


class QuestionStatus(str, enum.Enum):
    ACTIVE = "active"
    REPORTED = "reported"
    REMOVED = "removed"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
