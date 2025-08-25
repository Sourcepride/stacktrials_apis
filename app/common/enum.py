from enum import Enum


class Providers(str, Enum):
    GOOGLE = "google"
    GITHUB = "github"
    DROP_BOX = "dropbox"


# Enum classes for type safety
class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class CourseStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class EnrollmentType(str, Enum):
    OPEN = "open"
    RESTRICTED = "restricted"
    INVITATION_ONLY = "invitation_only"


class VisibilityType(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class ProgressionType(str, Enum):
    SEQUENTIAL = "sequential"
    FLEXIBLE = "flexible"


class ModuleType(str, Enum):
    VIDEO = "video"
    DOCUMENT = "document"
    QUIZ = "quiz"
    DISCUSSION = "discussion"
    EXTERNAL_LINK = "external_link"


class AttachmentType(str, Enum):
    DOCUMENT = "document"
    EXTERNAL_LINK = "external_link"


class VideoPlatform(str, Enum):
    YOUTUBE = "youtube"
    DAILYMOTION = "dailymotion"
    DROP_BOX = "dropbox"
    GOOGLE_DRIVE = "googledrive"


class DocumentPlatform(str, Enum):
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"
    DIRECT_LINK = "direct_link"


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"
    MATCHING = "matching"


class ShowResults(str, Enum):
    IMMEDIATE = "immediate"
    AFTER_SUBMISSION = "after_submission"
    AFTER_DUE_DATE = "after_due_date"


class EnrollmentStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    DROPPED = "dropped"
    SUSPENDED = "suspended"


class ModuleProgressStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class QuizAttemptStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class ChatType(str, Enum):
    DIRECT = "direct"
    GROUP = "group"


class GroupChatPrivacy(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    COURSE_REFERNCE = "reference"
    SYSTEM = "system"  # For system messages like "User joined the chat"


class MemberRole(str, Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    MEMBER = "member"


class MemberStatus(str, Enum):
    ACTIVE = "active"
    LEFT = "left"
    KICKED = "kicked"
    BANNED = "banned"


class SortCoursesBy(str, Enum):
    MOST_ENROLLED = "most_enrolled"
