"""modules/channel/whatsapp/bot.py — WhatsApp bot message handling logic.

Intent classification, handler routing, STOP opt-out, ADM escalation.
Processes incoming messages from agents and determines responses.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field

from modules.channel.whatsapp.provider import WhatsAppIncomingMessage

logger = logging.getLogger(__name__)


class Intent:
    """Detected intents from incoming agent messages."""
    STOP = "stop"
    TRAINING_REQUEST = "training_request"
    ADM_REQUEST = "adm_request"
    PRODUCT_QUESTION = "product_question"
    COMMISSION_QUESTION = "commission_question"
    COMPLAINT = "complaint"
    GREETING = "greeting"
    QUIZ_ANSWER = "quiz_answer"
    BUTTON_CLICK = "button_click"
    MEDIA_RECEIVED = "media_received"
    UNKNOWN = "unknown"


# Patterns for intent classification (Hindi + English)
_STOP_PATTERNS = re.compile(
    r"\b(stop|band|rok|ruko|unsubscribe|opt.?out|nahi\s+chahiye|mat\s+bhejo)\b",
    re.IGNORECASE,
)
_TRAINING_PATTERNS = re.compile(
    r"\b(training|lesson|sikho|sikhna|course|module|learn|padhai)\b",
    re.IGNORECASE,
)
_ADM_PATTERNS = re.compile(
    r"\b(adm|manager|sir|madam|baat\s+karni|call\s+kar|milna)\b",
    re.IGNORECASE,
)
_PRODUCT_PATTERNS = re.compile(
    r"\b(product|policy|plan|term|endowment|ulip|health|pension|bima|beema)\b",
    re.IGNORECASE,
)
_COMMISSION_PATTERNS = re.compile(
    r"\b(commission|payment|paise|paisa|income|earning|kamana|kamai)\b",
    re.IGNORECASE,
)
_COMPLAINT_PATTERNS = re.compile(
    r"\b(complaint|problem|issue|mushkil|dikkat|pareshani|galat|wrong)\b",
    re.IGNORECASE,
)
_GREETING_PATTERNS = re.compile(
    r"\b(hi|hello|hey|namaste|namaskar|good\s+morning|good\s+evening)\b",
    re.IGNORECASE,
)


@dataclass
class BotResponse:
    """Response the bot should send back to the agent."""
    text: str
    buttons: list[dict] | None = None
    escalate_to_adm: bool = False
    escalation_reason: str | None = None
    emit_consent_revoked: bool = False
    template_name: str | None = None
    template_params: dict | None = None


def classify_intent(message: WhatsAppIncomingMessage) -> str:
    """Classify the intent of an incoming message.

    Returns an Intent constant string.
    """
    # Button/interactive replies
    if message.message_type in ("button", "interactive") and message.button_payload:
        return Intent.BUTTON_CLICK

    # Media messages
    if message.message_type in ("image", "video", "document", "audio"):
        return Intent.MEDIA_RECEIVED

    text = (message.text or "").strip()
    if not text:
        return Intent.UNKNOWN

    # STOP opt-out takes highest priority
    if _STOP_PATTERNS.search(text):
        return Intent.STOP

    # Ordered by specificity
    if _COMMISSION_PATTERNS.search(text):
        return Intent.COMMISSION_QUESTION
    if _COMPLAINT_PATTERNS.search(text):
        return Intent.COMPLAINT
    if _PRODUCT_PATTERNS.search(text):
        return Intent.PRODUCT_QUESTION
    if _TRAINING_PATTERNS.search(text):
        return Intent.TRAINING_REQUEST
    if _ADM_PATTERNS.search(text):
        return Intent.ADM_REQUEST
    if _GREETING_PATTERNS.search(text):
        return Intent.GREETING

    return Intent.UNKNOWN


def handle_message(
    message: WhatsAppIncomingMessage,
    agent_name: str = "",
    adm_name: str = "",
    active_quiz: bool = False,
) -> BotResponse:
    """Process an incoming message and return the appropriate response.

    Args:
        message: The incoming WhatsApp message.
        agent_name: Agent's name for personalization.
        adm_name: ADM's name for referrals.
        active_quiz: Whether the agent has an active quiz session.
    """
    intent = classify_intent(message)

    # ─── STOP opt-out ───
    if intent == Intent.STOP:
        return BotResponse(
            text=(
                f"{agent_name} ji, aapki request samajh gayi. "
                "Ab hum aapko message nahi karenge. "
                "Agar future mein wapas aana chahein, toh 'START' type karein."
            ),
            emit_consent_revoked=True,
        )

    # ─── Button click / Quiz answer ───
    if intent == Intent.BUTTON_CLICK:
        payload = message.button_payload or ""
        # Quiz answers are handled by training.py — just acknowledge here
        if active_quiz or payload.startswith("quiz_"):
            return BotResponse(text="")  # Handled by training flow

        # Template button responses
        if payload in ("shuru_karein", "Shuru karein"):
            return BotResponse(text="Chaliye shuru karte hain!")
        if payload in ("baad_mein", "Baad mein"):
            return BotResponse(text="Koi baat nahi, jab chahein tab shuru kar sakte hain.")
        if payload in ("training_chahiye", "Training chahiye"):
            return BotResponse(
                text=f"{agent_name} ji, aapke liye training ready hai!",
            )
        if payload in ("adm_se_baat", "ADM se baat karni hai", "ADM se baat karein"):
            return BotResponse(
                text=f"Main {adm_name} ji ko bata deti hoon. Woh jald aapko call karenge.",
                escalate_to_adm=True,
                escalation_reason=f"Agent {agent_name} wants to talk to ADM",
            )
        if payload in ("sab_theek", "Sab theek hai"):
            return BotResponse(text="Accha sunta hoon! Koi zaroorat ho toh batayein.")

        # Generic button response
        return BotResponse(text="Samajh gaye, dhanyawaad!")

    # ─── Media messages ───
    if intent == Intent.MEDIA_RECEIVED:
        if message.message_type == "audio":
            return BotResponse(
                text="Aapka voice note mil gaya. Abhi hum ise process kar rahe hain.",
            )
        if message.message_type == "image":
            return BotResponse(
                text=(
                    "Aapki photo mil gayi. "
                    f"Agar isme koi madad chahiye toh {adm_name} ji ko bhejte hain."
                ),
                escalate_to_adm=True,
                escalation_reason=f"Agent {agent_name} sent an image",
            )
        return BotResponse(
            text="Aapka file mil gaya, dhanyawaad!",
        )

    # ─── Training request ───
    if intent == Intent.TRAINING_REQUEST:
        return BotResponse(
            text=f"{agent_name} ji, aapke liye training modules available hain!",
            buttons=[
                {"id": "start_training", "title": "Training shuru karein"},
                {"id": "view_modules", "title": "Modules dekhein"},
            ],
        )

    # ─── ADM request ───
    if intent == Intent.ADM_REQUEST:
        return BotResponse(
            text=f"Main {adm_name} ji ko abhi inform karti hoon. Woh jald aapse connect karenge.",
            escalate_to_adm=True,
            escalation_reason=f"Agent {agent_name} requested ADM contact",
        )

    # ─── Product question ───
    if intent == Intent.PRODUCT_QUESTION:
        return BotResponse(
            text=(
                f"{agent_name} ji, product ke baare mein accha sawaal hai. "
                "Aapke liye relevant training module suggest karti hoon."
            ),
            buttons=[
                {"id": "start_training", "title": "Training dekhein"},
                {"id": "ask_adm", "title": "ADM se poochein"},
            ],
        )

    # ─── Commission question ───
    if intent == Intent.COMMISSION_QUESTION:
        return BotResponse(
            text=(
                f"{agent_name} ji, commission se related jaankari ke liye "
                f"{adm_name} ji se baat karna best hoga."
            ),
            escalate_to_adm=True,
            escalation_reason=f"Agent {agent_name} has commission questions",
        )

    # ─── Complaint ───
    if intent == Intent.COMPLAINT:
        return BotResponse(
            text=(
                f"{agent_name} ji, aapki baat samajh gayi. "
                f"Main {adm_name} ji ko turant bata deti hoon."
            ),
            escalate_to_adm=True,
            escalation_reason=f"Agent {agent_name} raised a complaint: {message.text}",
        )

    # ─── Greeting ───
    if intent == Intent.GREETING:
        return BotResponse(
            text=f"Namaste {agent_name} ji! Kaise hain aap? Kismein madad kar sakti hoon?",
            buttons=[
                {"id": "training_chahiye", "title": "Training chahiye"},
                {"id": "adm_se_baat", "title": "ADM se baat karein"},
                {"id": "sab_theek", "title": "Sab theek hai"},
            ],
        )

    # ─── Unknown / free text ───
    return BotResponse(
        text=(
            f"{agent_name} ji, main insurance se related sawaalon mein madad kar sakti hoon. "
            "Aap kya jaanna chahenge?"
        ),
        buttons=[
            {"id": "training_chahiye", "title": "Training chahiye"},
            {"id": "adm_se_baat", "title": "ADM se baat karein"},
        ],
    )
