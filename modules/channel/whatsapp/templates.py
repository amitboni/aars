"""modules/channel/whatsapp/templates.py — WhatsApp message template definitions.

Pre-approved templates for outbound messages (required outside the 24-hour reply window).
Each template has Hindi (hi) and English (en) variants.
render_template() resolves placeholders and selects the correct variant.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TemplateDefinition:
    """A single WhatsApp message template with language variants."""
    name: str
    category: str  # UTILITY, MARKETING
    variants: dict[str, str]  # lang_code -> template body with {placeholders}
    buttons: list[str] = field(default_factory=list)


# ─── Template Registry ────────────────────────────────────────────────────────

TEMPLATES: dict[str, TemplateDefinition] = {}


def _register(t: TemplateDefinition) -> TemplateDefinition:
    TEMPLATES[t.name] = t
    return t


# 1) Welcome new agent
_register(TemplateDefinition(
    name="welcome_new_agent",
    category="UTILITY",
    variants={
        "hi": (
            "{agent_name} ji, {company_name} mein aapka swagat hai!\n"
            "Aapke ADM {adm_name} ji hain — woh jald aapse milenge.\n\n"
            "Shuru karne ke liye, yeh 2 minute ka video dekhein."
        ),
        "en": (
            "Welcome {agent_name}! You are now part of {company_name}.\n"
            "Your ADM is {adm_name} — they will connect with you soon.\n\n"
            "Watch this 2-minute video to get started."
        ),
    },
    buttons=["Video dekhein", "ADM se baat karein"],
))

# 2) Training nudge
_register(TemplateDefinition(
    name="training_nudge",
    category="UTILITY",
    variants={
        "hi": (
            "{agent_name} ji, aapke liye ek naya lesson taiyaar hai:\n\n"
            "{module_name}\n"
            "{duration} minute\n\n"
            "{module_description}"
        ),
        "en": (
            "{agent_name}, a new lesson is ready for you:\n\n"
            "{module_name}\n"
            "{duration} minutes\n\n"
            "{module_description}"
        ),
    },
    buttons=["Shuru karein", "Baad mein"],
))

# 3) Training quiz
_register(TemplateDefinition(
    name="training_quiz",
    category="UTILITY",
    variants={
        "hi": (
            "Chaliye dekhte hain kitna yaad raha!\n\n"
            "Sawaal {question_number}/{total_questions}:\n"
            "{question_text}"
        ),
        "en": (
            "Let's see how much you remember!\n\n"
            "Question {question_number}/{total_questions}:\n"
            "{question_text}"
        ),
    },
    buttons=[],  # Dynamic — set per question
))

# 4) Training result — high score
_register(TemplateDefinition(
    name="training_result_high",
    category="UTILITY",
    variants={
        "hi": (
            "Shaandaar! Aapne {score}% score kiya!\n"
            "{module_name} complete ho gaya."
        ),
        "en": (
            "Excellent! You scored {score}%!\n"
            "{module_name} is now complete."
        ),
    },
))

# 5) Training result — medium score
_register(TemplateDefinition(
    name="training_result_medium",
    category="UTILITY",
    variants={
        "hi": (
            "Accha prayas! {score}% score.\n"
            "{weak_topic} par ek aur baar dekhein toh aur accha hoga."
        ),
        "en": (
            "Good effort! {score}% score.\n"
            "Reviewing {weak_topic} once more will help."
        ),
    },
))

# 6) Training result — low score
_register(TemplateDefinition(
    name="training_result_low",
    category="UTILITY",
    variants={
        "hi": (
            "Koi baat nahi, {score}% score aaya.\n"
            "Chaliye {weak_topic} phir se dekhte hain — yeh bahut zaroori topic hai."
        ),
        "en": (
            "No worries, you scored {score}%.\n"
            "Let's review {weak_topic} again — it's an important topic."
        ),
    },
))

# 7) Gentle check-in
_register(TemplateDefinition(
    name="gentle_checkin",
    category="UTILITY",
    variants={
        "hi": (
            "{agent_name} ji, kaise hain aap?\n\n"
            "{contextual_message}\n\n"
            "Kya koi cheez hai jismein hum madad kar sakein?"
        ),
        "en": (
            "Hi {agent_name}, how are you?\n\n"
            "{contextual_message}\n\n"
            "Is there anything we can help with?"
        ),
    },
    buttons=["Training chahiye", "ADM se baat karni hai", "Sab theek hai"],
))

# 8) Sale congratulation
_register(TemplateDefinition(
    name="sale_congratulation",
    category="UTILITY",
    variants={
        "hi": (
            "Badhai ho {agent_name} ji!\n\n"
            "Aapki {product_name} policy issue ho gayi!\n"
            "Commission: Rs.{estimated_commission} (estimate)\n\n"
            "Aage aur bhi sales aayengi!"
        ),
        "en": (
            "Congratulations {agent_name}!\n\n"
            "Your {product_name} policy has been issued!\n"
            "Commission: Rs.{estimated_commission} (estimate)\n\n"
            "More sales coming your way!"
        ),
    },
))

# 9) License expiry reminder
_register(TemplateDefinition(
    name="license_expiry_reminder",
    category="UTILITY",
    variants={
        "hi": (
            "{agent_name} ji, aapka IRDAI license {expiry_date} ko expire ho raha hai.\n\n"
            "Renewal ke liye {remaining_hours} ghante training baaki hai.\n"
            "Abhi shuru karein — sab WhatsApp par hi ho jaayega."
        ),
        "en": (
            "{agent_name}, your IRDAI license expires on {expiry_date}.\n\n"
            "{remaining_hours} hours of training remaining for renewal.\n"
            "Start now — everything can be done right here on WhatsApp."
        ),
    },
    buttons=["Training shuru karein", "Details chahiye"],
))

# 10) ADM-attributed personalized message
_register(TemplateDefinition(
    name="adm_personalized",
    category="UTILITY",
    variants={
        "hi": (
            "{agent_name} ji, main {adm_name}.\n\n"
            "{personalized_message}\n\n"
            "Koi sawaal ho toh bataiye."
        ),
        "en": (
            "{agent_name}, this is {adm_name}.\n\n"
            "{personalized_message}\n\n"
            "Let me know if you have any questions."
        ),
    },
))


def render_template(
    template_name: str,
    language: str = "hi",
    params: dict | None = None,
) -> str | None:
    """Render a template with given parameters.

    Returns None if the template or language variant doesn't exist.
    Unknown placeholders are left as-is (they'll be caught in testing).
    """
    template = TEMPLATES.get(template_name)
    if not template:
        return None

    body = template.variants.get(language)
    if body is None:
        # Fall back to Hindi if requested language unavailable
        body = template.variants.get("hi")
    if body is None:
        return None

    if params:
        for key, value in params.items():
            body = body.replace(f"{{{key}}}", str(value))

    return body


def get_template_buttons(template_name: str) -> list[str]:
    """Return the default button labels for a template."""
    template = TEMPLATES.get(template_name)
    if template:
        return list(template.buttons)
    return []


def get_training_result_template(score: float) -> str:
    """Select the appropriate training result template based on score."""
    if score >= 80:
        return "training_result_high"
    elif score >= 50:
        return "training_result_medium"
    else:
        return "training_result_low"


async def render_template_from_db(
    db,
    tenant_id,
    template_name: str,
    language: str = "hi",
    params: dict | None = None,
) -> str | None:
    """Render template from database. Falls back to hardcoded TEMPLATES if not found.

    Args:
        db: AsyncSession from FastAPI dependency injection.
        tenant_id: UUID of the tenant.
        template_name: Template name to look up.
        language: Language code (e.g. "hi", "en").
        params: Dict of placeholder values to substitute.

    Returns:
        Rendered message string, or None if template not found anywhere.
    """
    from modules.content.service import get_active_template_by_name

    result = await get_active_template_by_name(db, tenant_id, template_name, language)
    if result:
        _template, body = result
        if params:
            for key, value in params.items():
                body = body.replace(f"{{{key}}}", str(value))
        return body

    # Fall back to hardcoded TEMPLATES dict
    return render_template(template_name, language, params)
