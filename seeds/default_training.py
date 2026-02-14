"""seeds/default_training.py — Default training module content.

Seed training modules with: title, description, topic, duration_minutes,
difficulty, quiz_questions. These are stubs — real content would come from
the insurer's LMS integration.
"""
from __future__ import annotations

from core.enums import TrainingTopic


def get_default_training_modules() -> list[dict]:
    """Return default training module definitions."""
    return [
        {
            "title": "Term Life Insurance Basics",
            "description": (
                "Learn the fundamentals of term life insurance — what it covers, "
                "who it's for, key features, and how to explain it to customers."
            ),
            "topic": TrainingTopic.PRODUCT_TERM_LIFE,
            "duration_minutes": 3,
            "difficulty": "BEGINNER",
            "content_url": "https://training.example.com/term-life-basics",
            "content_type": "video",
            "quiz_questions": [
                {
                    "question": "What does term life insurance primarily provide?",
                    "options": ["Investment returns", "Death benefit for a fixed period", "Health coverage", "Pension"],
                    "correct": 1,
                },
                {
                    "question": "Who is the ideal customer for term life?",
                    "options": ["Retired persons", "Young earning members with dependents", "Children", "NRIs only"],
                    "correct": 1,
                },
                {
                    "question": "What happens if the policyholder survives the term?",
                    "options": ["Gets double the sum assured", "Nothing — pure protection", "Gets maturity bonus", "Premium refunded"],
                    "correct": 1,
                },
                {
                    "question": "What is the main advantage of term life over whole life?",
                    "options": ["Higher investment returns", "Lower premium for same coverage", "No medical exam needed", "Guaranteed bonus"],
                    "correct": 1,
                },
                {
                    "question": "At what age should one ideally buy term insurance?",
                    "options": ["After retirement", "As early as possible", "Only after marriage", "After age 50"],
                    "correct": 1,
                },
            ],
        },
        {
            "title": "Endowment Plans Explained",
            "description": (
                "Understand endowment plans — the combination of insurance and savings, "
                "maturity benefits, bonus structure, and ideal customer profiles."
            ),
            "topic": TrainingTopic.PRODUCT_ENDOWMENT,
            "duration_minutes": 4,
            "difficulty": "BEGINNER",
            "content_url": "https://training.example.com/endowment-explained",
            "content_type": "video",
            "quiz_questions": [
                {
                    "question": "What does an endowment plan offer that term life doesn't?",
                    "options": ["Lower premium", "Maturity benefit", "Higher death cover", "Group coverage"],
                    "correct": 1,
                },
                {
                    "question": "What is a reversionary bonus?",
                    "options": ["Penalty for late payment", "Annual bonus added to sum assured", "Tax benefit", "Referral reward"],
                    "correct": 1,
                },
                {
                    "question": "Who is the ideal customer for endowment?",
                    "options": ["High-risk investors", "Conservative savers wanting insurance + savings", "Day traders", "Corporate clients"],
                    "correct": 1,
                },
            ],
        },
        {
            "title": "ULIP Simplified",
            "description": (
                "Learn about Unit Linked Insurance Plans — how they combine insurance "
                "with market-linked investments, fund options, and charges."
            ),
            "topic": TrainingTopic.PRODUCT_ULIP,
            "duration_minutes": 5,
            "difficulty": "INTERMEDIATE",
            "content_url": "https://training.example.com/ulip-simplified",
            "content_type": "video",
            "quiz_questions": [
                {
                    "question": "What makes ULIP different from traditional plans?",
                    "options": ["No insurance component", "Market-linked investment", "Only for corporates", "No lock-in period"],
                    "correct": 1,
                },
                {
                    "question": "What is the lock-in period for ULIPs?",
                    "options": ["1 year", "3 years", "5 years", "10 years"],
                    "correct": 2,
                },
                {
                    "question": "What are the fund options in ULIP?",
                    "options": ["Only equity", "Only debt", "Equity, debt, and balanced", "Only gold"],
                    "correct": 2,
                },
            ],
        },
        {
            "title": "Sales Pitch Techniques",
            "description": (
                "Master the art of insurance sales pitches — understanding customer needs, "
                "building rapport, presenting solutions, and closing the deal."
            ),
            "topic": TrainingTopic.SALES_PITCH,
            "duration_minutes": 4,
            "difficulty": "BEGINNER",
            "content_url": "https://training.example.com/sales-pitch",
            "content_type": "video",
            "quiz_questions": [
                {
                    "question": "What should be the first step in a sales conversation?",
                    "options": ["Present the product", "Ask about customer needs", "Quote the premium", "Show brochure"],
                    "correct": 1,
                },
                {
                    "question": "How should you handle a customer who says 'I'll think about it'?",
                    "options": ["Walk away", "Pressure them", "Address specific concerns and set follow-up", "Offer discount"],
                    "correct": 2,
                },
                {
                    "question": "What builds customer trust the most?",
                    "options": ["Fancy brochures", "Listening to their needs", "Offering lowest premium", "Making promises"],
                    "correct": 1,
                },
            ],
        },
        {
            "title": "Objection Handling Masterclass",
            "description": (
                "Learn to handle the most common customer objections in insurance sales — "
                "'too expensive', 'I don't need it', 'I already have insurance', etc."
            ),
            "topic": TrainingTopic.SALES_OBJECTION_HANDLING,
            "duration_minutes": 5,
            "difficulty": "INTERMEDIATE",
            "content_url": "https://training.example.com/objection-handling",
            "content_type": "video",
            "quiz_questions": [
                {
                    "question": "When a customer says 'Insurance is too expensive', you should:",
                    "options": ["Agree with them", "Show cost per day and value", "Offer a different product", "End the conversation"],
                    "correct": 1,
                },
                {
                    "question": "What's the best response to 'I already have insurance'?",
                    "options": ["OK goodbye", "Ask about coverage gaps", "Say theirs is bad", "Ignore and pitch"],
                    "correct": 1,
                },
            ],
        },
        {
            "title": "Proposal Form Filling Guide",
            "description": (
                "Step-by-step guide to correctly filling out insurance proposal forms — "
                "common mistakes to avoid, required documents, and submission process."
            ),
            "topic": TrainingTopic.PROCESS_PROPOSAL_FILLING,
            "duration_minutes": 3,
            "difficulty": "BEGINNER",
            "content_url": "https://training.example.com/proposal-form-guide",
            "content_type": "video",
            "quiz_questions": [
                {
                    "question": "What happens if the proposal form has incorrect information?",
                    "options": ["Nothing", "Claim may be rejected", "Premium goes up", "Policy auto-cancels"],
                    "correct": 1,
                },
                {
                    "question": "Which document is mandatory for KYC?",
                    "options": ["Ration card only", "Photo ID + Address proof", "Passport only", "Driving license only"],
                    "correct": 1,
                },
            ],
        },
        {
            "title": "KYC Process and Requirements",
            "description": (
                "Understand Know Your Customer (KYC) requirements for insurance — "
                "acceptable documents, digital KYC options, and compliance requirements."
            ),
            "topic": TrainingTopic.PROCESS_KYC,
            "duration_minutes": 3,
            "difficulty": "BEGINNER",
            "content_url": "https://training.example.com/kyc-process",
            "content_type": "video",
            "quiz_questions": [
                {
                    "question": "What is KYC in insurance?",
                    "options": ["A type of policy", "Customer identity verification", "A premium calculator", "An investment fund"],
                    "correct": 1,
                },
                {
                    "question": "Can KYC be done digitally?",
                    "options": ["No, only physical", "Yes, via Aadhaar-based eKYC", "Only for ULIPs", "Only for term plans"],
                    "correct": 1,
                },
            ],
        },
    ]
