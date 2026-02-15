"""modules/content/seed_templates.py — Default message template seed data.

10 realistic insurance communication templates with full Hindi and English content.
"""
from __future__ import annotations


def get_default_templates() -> list[dict]:
    """Return default message template definitions for seeding."""
    return [
        # 1) Welcome new agent
        {
            "name": "welcome_new_agent",
            "category": "welcome",
            "description": "Welcome message sent to newly onboarded agents",
            "language_variants": {
                "hi": (
                    "\U0001f389 स्वागत है {agent_name} जी! आप {company_name} परिवार का हिस्सा बन गए हैं। "
                    "हम आपकी इस नई यात्रा में हर कदम पर साथ हैं। "
                    "कोई भी सवाल हो तो बेझिझक पूछें!"
                ),
                "en": (
                    "\U0001f389 Welcome {agent_name}! You are now part of the {company_name} family. "
                    "We are with you every step of this journey. "
                    "Feel free to ask any questions!"
                ),
            },
            "placeholders": [
                {"key": "agent_name", "description": "Agent's full name", "required": True},
                {"key": "company_name", "description": "Insurance company name", "required": True},
            ],
            "buttons": [
                {"label": "Training shuru karein", "type": "quick_reply"},
                {"label": "Products dekhein", "type": "quick_reply"},
            ],
            "status": "active",
            "is_default": True,
        },
        # 2) Training nudge
        {
            "name": "training_nudge",
            "category": "training",
            "description": "Nudge to encourage agents to start a new training module",
            "language_variants": {
                "hi": (
                    "{agent_name} जी, आपके लिए एक नया lesson तैयार है:\n\n"
                    "\U0001f4da {module_name}\n"
                    "\u23f1\ufe0f सिर्फ {duration_minutes} minute\n\n"
                    "Yeh module aapki selling skills ko next level pe le jaayega!"
                ),
                "en": (
                    "{agent_name}, a new lesson is ready for you:\n\n"
                    "\U0001f4da {module_name}\n"
                    "\u23f1\ufe0f Just {duration_minutes} minutes\n\n"
                    "This module will take your selling skills to the next level!"
                ),
            },
            "placeholders": [
                {"key": "agent_name", "description": "Agent's full name", "required": True},
                {"key": "module_name", "description": "Training module title", "required": True},
                {"key": "duration_minutes", "description": "Module duration in minutes", "required": True},
            ],
            "buttons": [
                {"label": "Abhi shuru karein", "type": "quick_reply"},
                {"label": "Baad mein", "type": "quick_reply"},
            ],
            "status": "active",
            "is_default": True,
        },
        # 3) Training quiz
        {
            "name": "training_quiz",
            "category": "training",
            "description": "Quiz question sent during training flow",
            "language_variants": {
                "hi": (
                    "चलिए देखते हैं कितना याद रहा! \U0001f9e0\n\n"
                    "सवाल {question_number}/{total_questions}:\n"
                    "{question_text}"
                ),
                "en": (
                    "Let's see how much you remember! \U0001f9e0\n\n"
                    "Question {question_number}/{total_questions}:\n"
                    "{question_text}"
                ),
            },
            "placeholders": [
                {"key": "question_number", "description": "Current question number", "required": True},
                {"key": "total_questions", "description": "Total number of questions", "required": True},
                {"key": "question_text", "description": "The quiz question text", "required": True},
            ],
            "buttons": [],
            "status": "active",
            "is_default": True,
        },
        # 4) Training result — high score
        {
            "name": "training_result_high",
            "category": "training",
            "description": "Congratulation message for high quiz scores (>=80%)",
            "language_variants": {
                "hi": (
                    "\U0001f31f शानदार {agent_name} जी! आपने {score}% score किया!\n\n"
                    "{module_name} complete हो गया। "
                    "आप तैयार हैं customers से बात करने के लिए!"
                ),
                "en": (
                    "\U0001f31f Excellent {agent_name}! You scored {score}%!\n\n"
                    "{module_name} is complete. "
                    "You're ready to talk to customers!"
                ),
            },
            "placeholders": [
                {"key": "agent_name", "description": "Agent's full name", "required": True},
                {"key": "score", "description": "Quiz score percentage", "required": True},
                {"key": "module_name", "description": "Training module title", "required": True},
            ],
            "buttons": [],
            "status": "active",
            "is_default": True,
        },
        # 5) Training result — medium score
        {
            "name": "training_result_medium",
            "category": "training",
            "description": "Encouragement message for medium quiz scores (50-79%)",
            "language_variants": {
                "hi": (
                    "अच्छा प्रयास {agent_name} जी! {score}% score आया।\n\n"
                    "{module_name} के कुछ points दोबारा review करें "
                    "तो aur better ho jaayega!"
                ),
                "en": (
                    "Good effort {agent_name}! You scored {score}%.\n\n"
                    "Review a few points from {module_name} "
                    "and you'll do even better!"
                ),
            },
            "placeholders": [
                {"key": "agent_name", "description": "Agent's full name", "required": True},
                {"key": "score", "description": "Quiz score percentage", "required": True},
                {"key": "module_name", "description": "Training module title", "required": True},
            ],
            "buttons": [
                {"label": "Dobara try karein", "type": "quick_reply"},
                {"label": "Agle module pe jaayein", "type": "quick_reply"},
            ],
            "status": "active",
            "is_default": True,
        },
        # 6) Training result — low score
        {
            "name": "training_result_low",
            "category": "training",
            "description": "Supportive message for low quiz scores (<50%)",
            "language_variants": {
                "hi": (
                    "कोई बात नहीं {agent_name} जी! {score}% score aaya.\n\n"
                    "{module_name} ka video ek baar aur dekhein, phir quiz dein. "
                    "Practice se perfect hota hai! \U0001f4aa"
                ),
                "en": (
                    "No worries {agent_name}! You scored {score}%.\n\n"
                    "Watch the {module_name} video once more, then retake the quiz. "
                    "Practice makes perfect! \U0001f4aa"
                ),
            },
            "placeholders": [
                {"key": "agent_name", "description": "Agent's full name", "required": True},
                {"key": "score", "description": "Quiz score percentage", "required": True},
                {"key": "module_name", "description": "Training module title", "required": True},
            ],
            "buttons": [
                {"label": "Video dekhein", "type": "quick_reply"},
                {"label": "Quiz dobara dein", "type": "quick_reply"},
            ],
            "status": "active",
            "is_default": True,
        },
        # 7) Gentle check-in
        {
            "name": "gentle_checkin",
            "category": "engagement",
            "description": "Periodic check-in message to maintain engagement",
            "language_variants": {
                "hi": (
                    "{agent_name} जी, कैसे हैं आप?\n\n"
                    "{contextual_message}\n\n"
                    "Koi bhi madad chahiye toh hum yahan hain!"
                ),
                "en": (
                    "{agent_name}, how are you doing?\n\n"
                    "{contextual_message}\n\n"
                    "We're here if you need any help!"
                ),
            },
            "placeholders": [
                {"key": "agent_name", "description": "Agent's full name", "required": True},
                {"key": "contextual_message", "description": "Context-specific message body", "required": True},
            ],
            "buttons": [
                {"label": "Sab theek hai", "type": "quick_reply"},
                {"label": "Madad chahiye", "type": "quick_reply"},
                {"label": "Training chahiye", "type": "quick_reply"},
            ],
            "status": "active",
            "is_default": True,
        },
        # 8) Sale congratulation
        {
            "name": "sale_congratulation",
            "category": "celebration",
            "description": "Congratulation message when an agent's policy is issued",
            "language_variants": {
                "hi": (
                    "\U0001f38a बधाई हो {agent_name} जी!\n\n"
                    "आपकी {product_name} policy ({policy_number}) issue हो गई! "
                    "Yeh aapki mehnat ka nateeja hai.\n\n"
                    "Aise hi aage badhte rahein! \U0001f680"
                ),
                "en": (
                    "\U0001f38a Congratulations {agent_name}!\n\n"
                    "Your {product_name} policy ({policy_number}) has been issued! "
                    "This is the result of your hard work.\n\n"
                    "Keep going! \U0001f680"
                ),
            },
            "placeholders": [
                {"key": "agent_name", "description": "Agent's full name", "required": True},
                {"key": "product_name", "description": "Insurance product name", "required": True},
                {"key": "policy_number", "description": "Issued policy number", "required": True},
            ],
            "buttons": [
                {"label": "Agla target dekhein", "type": "quick_reply"},
            ],
            "status": "active",
            "is_default": True,
        },
        # 9) License expiry reminder
        {
            "name": "license_expiry_reminder",
            "category": "reminder",
            "description": "Reminder when IRDAI license is approaching expiry",
            "language_variants": {
                "hi": (
                    "\u26a0\ufe0f {agent_name} जी, आपका IRDAI license {expiry_date} को expire हो रहा है।\n\n"
                    "{days_remaining} din baaki hain. "
                    "Abhi renewal process shuru karein taki koi dikkat na ho."
                ),
                "en": (
                    "\u26a0\ufe0f {agent_name}, your IRDAI license expires on {expiry_date}.\n\n"
                    "{days_remaining} days remaining. "
                    "Start the renewal process now to avoid any issues."
                ),
            },
            "placeholders": [
                {"key": "agent_name", "description": "Agent's full name", "required": True},
                {"key": "expiry_date", "description": "License expiry date", "required": True},
                {"key": "days_remaining", "description": "Number of days until expiry", "required": True},
            ],
            "buttons": [
                {"label": "Renewal process dekhein", "type": "quick_reply"},
                {"label": "Madad chahiye", "type": "quick_reply"},
            ],
            "status": "active",
            "is_default": True,
        },
        # 10) ADM personalized message
        {
            "name": "adm_personalized",
            "category": "adm",
            "description": "Personalized message sent on behalf of the ADM (Agency Development Manager)",
            "language_variants": {
                "hi": (
                    "{agent_name} जी, मैं {adm_name}।\n\n"
                    "{personalized_message}\n\n"
                    "Koi bhi sawaal ho toh mujhe message karein."
                ),
                "en": (
                    "{agent_name}, this is {adm_name}.\n\n"
                    "{personalized_message}\n\n"
                    "Feel free to message me with any questions."
                ),
            },
            "placeholders": [
                {"key": "agent_name", "description": "Agent's full name", "required": True},
                {"key": "adm_name", "description": "ADM's name", "required": True},
                {"key": "personalized_message", "description": "Custom message from the ADM", "required": True},
            ],
            "buttons": [
                {"label": "Call karein", "type": "quick_reply"},
                {"label": "Theek hai", "type": "quick_reply"},
            ],
            "status": "active",
            "is_default": True,
        },
    ]
