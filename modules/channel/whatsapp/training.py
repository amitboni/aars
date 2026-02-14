"""modules/channel/whatsapp/training.py — Training quiz flow over WhatsApp.

Micro-module delivery: intro -> content -> quiz -> result.
Quiz state tracking per agent, immediate feedback, score calculation.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class QuizQuestion:
    """A single quiz question."""
    question_text: str
    options: list[str]  # Max 3 for WhatsApp buttons
    correct_index: int  # 0-based index into options


@dataclass
class TrainingModule:
    """A micro-module for WhatsApp delivery."""
    module_id: str
    module_name: str
    description: str
    duration_minutes: int
    content_url: str | None = None  # Video or infographic URL
    content_type: str = "video"  # video, infographic
    questions: list[QuizQuestion] = field(default_factory=list)
    language: str = "hi"


@dataclass
class QuizState:
    """Tracks an agent's progress through a quiz."""
    agent_id: uuid.UUID
    tenant_id: uuid.UUID
    module_id: str
    module_name: str
    questions: list[QuizQuestion]
    current_question: int = 0  # 0-based
    answers: list[int | None] = field(default_factory=list)  # Selected option indices
    correct_count: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.answers:
            self.answers = [None] * len(self.questions)

    @property
    def is_complete(self) -> bool:
        return self.current_question >= len(self.questions)

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    @property
    def score_percent(self) -> float:
        if not self.questions:
            return 0.0
        return round((self.correct_count / len(self.questions)) * 100, 1)


@dataclass
class QuizStepResult:
    """Result from processing a quiz step."""
    text: str
    buttons: list[dict] | None = None
    is_complete: bool = False
    score_percent: float = 0.0
    correct_count: int = 0
    total_questions: int = 0


# ─── In-memory quiz state store (Redis-backed in production) ──────────────────

_active_quizzes: dict[str, QuizState] = {}  # key: "{tenant_id}:{agent_id}"


def _quiz_key(tenant_id: uuid.UUID, agent_id: uuid.UUID) -> str:
    return f"{tenant_id}:{agent_id}"


def get_active_quiz(tenant_id: uuid.UUID, agent_id: uuid.UUID) -> QuizState | None:
    """Get the active quiz state for an agent, if any."""
    return _active_quizzes.get(_quiz_key(tenant_id, agent_id))


def has_active_quiz(tenant_id: uuid.UUID, agent_id: uuid.UUID) -> bool:
    """Check whether the agent has an active quiz session."""
    return _quiz_key(tenant_id, agent_id) in _active_quizzes


def start_quiz(
    tenant_id: uuid.UUID,
    agent_id: uuid.UUID,
    module: TrainingModule,
) -> QuizStepResult:
    """Start a quiz for an agent. Returns the first question."""
    if not module.questions:
        return QuizStepResult(
            text=f"{module.module_name} mein koi quiz nahi hai. Module complete!",
            is_complete=True,
        )

    state = QuizState(
        agent_id=agent_id,
        tenant_id=tenant_id,
        module_id=module.module_id,
        module_name=module.module_name,
        questions=module.questions,
    )
    _active_quizzes[_quiz_key(tenant_id, agent_id)] = state

    return _format_question(state)


def process_quiz_answer(
    tenant_id: uuid.UUID,
    agent_id: uuid.UUID,
    answer_index: int,
) -> QuizStepResult:
    """Process a quiz answer and return feedback + next question or result.

    Args:
        tenant_id: Tenant UUID.
        agent_id: Agent UUID.
        answer_index: 0-based index of the selected option.
    """
    key = _quiz_key(tenant_id, agent_id)
    state = _active_quizzes.get(key)
    if not state:
        return QuizStepResult(
            text="Koi active quiz nahi hai. Training shuru karne ke liye 'Training chahiye' bhejein.",
        )

    if state.is_complete:
        _active_quizzes.pop(key, None)
        return _format_result(state)

    # Record answer
    question = state.questions[state.current_question]
    is_correct = answer_index == question.correct_index
    state.answers[state.current_question] = answer_index
    if is_correct:
        state.correct_count += 1

    # Immediate feedback
    if is_correct:
        feedback = "Sahi jawaab! "
    else:
        correct_option = question.options[question.correct_index]
        feedback = f"Sahi jawaab tha: {correct_option}. "

    # Move to next question
    state.current_question += 1

    if state.is_complete:
        state.completed_at = datetime.now(timezone.utc)
        result = _format_result(state)
        result.text = feedback + "\n\n" + result.text
        _active_quizzes.pop(key, None)
        return result

    # Next question
    next_q = _format_question(state)
    next_q.text = feedback + "\n\n" + next_q.text
    return next_q


def cancel_quiz(tenant_id: uuid.UUID, agent_id: uuid.UUID) -> None:
    """Cancel an active quiz for an agent."""
    _active_quizzes.pop(_quiz_key(tenant_id, agent_id), None)


def clear_all_quizzes() -> None:
    """Clear all active quizzes. Used in testing."""
    _active_quizzes.clear()


# ─── Formatting helpers ───────────────────────────────────────────────────────

def _format_question(state: QuizState) -> QuizStepResult:
    """Format the current question as a WhatsApp message."""
    q = state.questions[state.current_question]
    q_num = state.current_question + 1
    total = state.total_questions

    text = (
        f"Sawaal {q_num}/{total}:\n"
        f"{q.question_text}"
    )

    buttons = [
        {"id": f"quiz_{state.module_id}_{state.current_question}_{i}", "title": opt[:20]}
        for i, opt in enumerate(q.options[:3])  # WhatsApp max 3 buttons
    ]

    return QuizStepResult(
        text=text,
        buttons=buttons,
        total_questions=total,
    )


def _format_result(state: QuizState) -> QuizStepResult:
    """Format the quiz result as a WhatsApp message."""
    score = state.score_percent

    if score >= 80:
        text = (
            f"Shaandaar! Aapne {score:.0f}% score kiya!\n"
            f"{state.module_name} complete ho gaya."
        )
    elif score >= 50:
        text = (
            f"Accha prayas! {score:.0f}% score.\n"
            f"Thoda aur practice karein toh aur accha hoga."
        )
    else:
        text = (
            f"Koi baat nahi, {score:.0f}% score aaya.\n"
            f"Chaliye phir se dekhte hain — yeh important topic hai."
        )

    return QuizStepResult(
        text=text,
        is_complete=True,
        score_percent=score,
        correct_count=state.correct_count,
        total_questions=state.total_questions,
    )


def parse_quiz_button_payload(payload: str) -> tuple[str, int, int] | None:
    """Parse a quiz button payload into (module_id, question_index, answer_index).

    Expected format: quiz_{module_id}_{question_index}_{answer_index}
    Returns None if payload doesn't match quiz format.
    """
    if not payload.startswith("quiz_"):
        return None
    parts = payload.split("_")
    # quiz_{module_id}_{q_index}_{a_index} — module_id may contain underscores
    if len(parts) < 4:
        return None
    try:
        answer_index = int(parts[-1])
        question_index = int(parts[-2])
        module_id = "_".join(parts[1:-2])
        return module_id, question_index, answer_index
    except (ValueError, IndexError):
        return None
