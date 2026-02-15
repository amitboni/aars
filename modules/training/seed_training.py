"""modules/training/seed_training.py — Default training module seed data.

7 realistic insurance training modules with Hindi (Hinglish) quiz questions,
correct answer indexes, and explanations.
"""
from __future__ import annotations


def get_default_training_modules() -> list[dict]:
    """Return default training module definitions for seeding."""
    return [
        # 1) Term Life Insurance — Basics
        {
            "title": "Term Life Insurance — Basics",
            "description": (
                "Term life insurance kya hai, kaise kaam karta hai, "
                "aur customer ko kaise samjhayein — sab kuch is module mein."
            ),
            "topic": "product_term_life",
            "difficulty": "beginner",
            "duration_minutes": 30,
            "language": "hi",
            "content_type": "video",
            "questions": [
                {
                    "question": "Term life insurance mein maturity benefit milta hai?",
                    "options": ["Haan, poora sum assured milta hai", "Nahi, sirf death benefit milta hai", "Haan, bonus ke saath milta hai"],
                    "correct": 1,
                    "explanation": "Term life sirf death benefit deta hai, maturity pe kuch nahi milta. Isliye premium kam hota hai.",
                },
                {
                    "question": "Term insurance ka sabse bada fayda kya hai?",
                    "options": ["Investment returns", "Kam premium mein zyada coverage", "Tax-free maturity"],
                    "correct": 1,
                    "explanation": "Term insurance ka sabse bada fayda yeh hai ki bahut kam premium mein bada death cover milta hai.",
                },
                {
                    "question": "Term insurance kab lena chahiye?",
                    "options": ["Retirement ke baad", "Jitni jaldi ho sake — kam umar mein premium kam hota hai", "Shaadi ke baad hi"],
                    "correct": 1,
                    "explanation": "Jitni kam umar mein lein, utna kam premium hota hai. Jaldi lena best hai.",
                },
                {
                    "question": "Agar policyholder term ke baad zinda rahe toh kya hoga?",
                    "options": ["Premium wapas milega", "Kuch nahi milega — policy khatam", "Double sum assured milega"],
                    "correct": 1,
                    "explanation": "Pure term plan mein maturity benefit nahi hota. Policy simply expire ho jaati hai.",
                },
                {
                    "question": "Term insurance kis ke liye sabse zyada zaroori hai?",
                    "options": ["Retired log", "Kamane wale log jinke dependents hain", "Bacche", "NRI"],
                    "correct": 1,
                    "explanation": "Jinke family members unki income pe depend karte hain, unke liye term insurance sabse zaroori hai.",
                },
            ],
            "passing_score": 70,
            "is_default": True,
        },
        # 2) Endowment Plans — Samajhein Aur Bechein
        {
            "title": "Endowment Plans — Samajhein Aur Bechein",
            "description": (
                "Endowment plan ka structure, maturity benefits, bonus types, "
                "aur surrender value — customer ko convince karne ke liye sab kuch."
            ),
            "topic": "product_endowment",
            "difficulty": "beginner",
            "duration_minutes": 35,
            "language": "hi",
            "content_type": "video",
            "questions": [
                {
                    "question": "Endowment plan mein term life se alag kya milta hai?",
                    "options": ["Sirf death benefit", "Death benefit + maturity benefit", "Sirf tax benefit"],
                    "correct": 1,
                    "explanation": "Endowment plan mein dono milte hain — agar policyholder survive kare toh maturity benefit, aur nahi toh death benefit.",
                },
                {
                    "question": "Reversionary bonus kya hota hai?",
                    "options": ["Late payment ka penalty", "Har saal sum assured mein add hone wala bonus", "Tax refund", "Referral reward"],
                    "correct": 1,
                    "explanation": "Reversionary bonus har saal declare hota hai aur sum assured mein add hota jaata hai. Maturity ya death pe milta hai.",
                },
                {
                    "question": "Endowment plan ka surrender value kab milta hai?",
                    "options": ["Pehle din se", "Minimum 3 saal premium bharne ke baad", "Sirf maturity pe", "Kabhi nahi"],
                    "correct": 1,
                    "explanation": "Surrender value tab milta hai jab kam se kam 3 saal ka premium bhara ho. Usse pehle surrender karne pe kuch nahi milta.",
                },
            ],
            "passing_score": 70,
            "is_default": True,
        },
        # 3) ULIP — Unit Linked Insurance Plans
        {
            "title": "ULIP — Unit Linked Insurance Plans",
            "description": (
                "ULIP kaise kaam karta hai — insurance + market investment ka combination. "
                "Lock-in period, fund switching, NAV, aur charges samajhein."
            ),
            "topic": "product_ulip",
            "difficulty": "intermediate",
            "duration_minutes": 40,
            "language": "hi",
            "content_type": "video",
            "questions": [
                {
                    "question": "ULIP ka lock-in period kitne saal ka hota hai?",
                    "options": ["1 saal", "3 saal", "5 saal", "10 saal"],
                    "correct": 2,
                    "explanation": "IRDAI ke niyam ke anusaar ULIP ka lock-in period 5 saal ka hota hai. Isse pehle paisa nahi nikal sakte.",
                },
                {
                    "question": "ULIP mein fund switching ka matlab kya hai?",
                    "options": [
                        "Policy cancel karna",
                        "Ek fund se doosre fund mein paisa transfer karna",
                        "Premium badhana",
                    ],
                    "correct": 1,
                    "explanation": "Fund switching mein aap apna paisa equity fund se debt fund mein ya uske ulta transfer kar sakte hain, bina policy cancel kiye.",
                },
                {
                    "question": "ULIP mein NAV kya hota hai?",
                    "options": [
                        "New Account Value",
                        "Net Asset Value — fund ki ek unit ki value",
                        "National Average Value",
                    ],
                    "correct": 1,
                    "explanation": "NAV = Net Asset Value. Yeh batata hai ki aapke fund ki ek unit ki market value kya hai.",
                },
            ],
            "passing_score": 70,
            "is_default": True,
        },
        # 4) Sales Pitch — Pehli Mulaqaat
        {
            "title": "Sales Pitch — Pehli Mulaqaat",
            "description": (
                "Customer se pehli meeting kaise karein — needs samajhna, "
                "trust banana, aur sahi product suggest karna."
            ),
            "topic": "sales_pitch",
            "difficulty": "beginner",
            "duration_minutes": 25,
            "language": "hi",
            "content_type": "video",
            "questions": [
                {
                    "question": "Sales conversation ka pehla step kya hona chahiye?",
                    "options": ["Product ka brochure dikhana", "Customer ki needs samajhna", "Premium batana", "Company ke baare mein batana"],
                    "correct": 1,
                    "explanation": "Pehle customer ki zarooratein samjho — needs-based selling se trust banta hai aur conversion rate badhta hai.",
                },
                {
                    "question": "Customer ka trust banane ka sabse accha tarika kya hai?",
                    "options": ["Fancy brochure dikhana", "Unki baatein dhyan se sunna", "Sabse sasta premium offer karna", "Bahut saare promises karna"],
                    "correct": 1,
                    "explanation": "Active listening se customer ko lagta hai ki aap unki care karte hain. Trust ka foundation yahi hai.",
                },
                {
                    "question": "Pehli meeting mein kitne products recommend karne chahiye?",
                    "options": ["Jitne zyada ho sake", "1-2 jo customer ki need se match karein", "Koi bhi nahi, sirf relationship banao", "Company ka sabse mehnga product"],
                    "correct": 1,
                    "explanation": "Zyada options confuse karte hain. 1-2 relevant products suggest karo jo customer ki specific needs se match karein.",
                },
            ],
            "passing_score": 70,
            "is_default": True,
        },
        # 5) Objection Handling — Customer Ke Sawaalon Ka Jawaab
        {
            "title": "Objection Handling — Customer Ke Sawaalon Ka Jawaab",
            "description": (
                "Customer ke common objections ka jawaab kaise dein — "
                "'premium bahut zyada hai', 'mujhe insurance ki zaroorat nahi', "
                "'main baad mein lunga' jaise sawaalon ka smart jawab."
            ),
            "topic": "sales_objection_handling",
            "difficulty": "intermediate",
            "duration_minutes": 30,
            "language": "hi",
            "content_type": "video",
            "questions": [
                {
                    "question": "Customer bole 'premium bahut zyada hai' — aap kya kahenge?",
                    "options": [
                        "Haan, premium toh zyada hai",
                        "Per day cost batayein aur value explain karein",
                        "Doosri company suggest karein",
                    ],
                    "correct": 1,
                    "explanation": "Premium ko per day mein todein — 'sirf Rs.30 per day mein aapki family ka Rs.1 crore ka cover'. Value perspective se customer samajhta hai.",
                },
                {
                    "question": "Customer bole 'mujhe insurance ki zaroorat nahi' — best response kya hai?",
                    "options": [
                        "OK, phir nahi chahiye toh rehne do",
                        "Unke dependents ke baare mein baat karein — 'aapke bacche kaise manage karenge?'",
                        "Jabardasti policy bechein",
                    ],
                    "correct": 1,
                    "explanation": "Insurance ki zaroorat seedha nahi dikhti. Dependents ki safety ke angle se baat karein — emotional connection banayein.",
                },
                {
                    "question": "Customer bole 'main baad mein lunga' — aap kya kahenge?",
                    "options": [
                        "Theek hai, jab mann kare tab lena",
                        "Aaj ki umar mein premium kam hai, baad mein badhega — aur health bhi change ho sakti hai",
                        "Aaj hi lena padega, kal mauka nahi milega",
                    ],
                    "correct": 1,
                    "explanation": "Factual approach use karein — umar badhne se premium badhta hai aur health conditions se insurance milna mushkil ho sakta hai.",
                },
            ],
            "passing_score": 70,
            "is_default": True,
        },
        # 6) Proposal Form — Sahi Tarike Se Bharein
        {
            "title": "Proposal Form — Sahi Tarike Se Bharein",
            "description": (
                "Insurance proposal form kaise bharein — common mistakes, "
                "zaroori documents, nominee details, aur submission process."
            ),
            "topic": "process_proposal_filling",
            "difficulty": "beginner",
            "duration_minutes": 20,
            "language": "hi",
            "content_type": "video",
            "questions": [
                {
                    "question": "Proposal form mein galat information dene se kya hoga?",
                    "options": [
                        "Kuch nahi hoga",
                        "Claim reject ho sakta hai — mis-representation ke ground pe",
                        "Premium kam ho jaayega",
                    ],
                    "correct": 1,
                    "explanation": "Galat information dena mis-representation hai. Claim ke time company reject kar sakti hai. Hamesha sahi information bharein.",
                },
                {
                    "question": "Nominee kaun ho sakta hai?",
                    "options": [
                        "Sirf wife ya husband",
                        "Koi bhi family member ya specified person",
                        "Sirf bacche",
                    ],
                    "correct": 1,
                    "explanation": "Nominee koi bhi ho sakta hai — spouse, parents, children, ya koi aur. Minor nominee ke liye appointee zaroori hai.",
                },
                {
                    "question": "Proposal form submit karne se pehle kya check karna zaroori hai?",
                    "options": [
                        "Sirf sign hai ya nahi",
                        "Saari details sahi hain, documents attached hain, sign complete hai",
                        "Sirf premium amount",
                    ],
                    "correct": 1,
                    "explanation": "Submit karne se pehle saari personal details, medical history, nominee info, attached documents, aur signatures verify karein.",
                },
            ],
            "passing_score": 70,
            "is_default": True,
        },
        # 7) KYC Process Aur Requirements
        {
            "title": "KYC Process Aur Requirements",
            "description": (
                "KYC kya hai, kaunse documents chahiye, e-KYC kaise kaam karta hai, "
                "aur PAN/Aadhaar requirements — sab kuch ek jagah."
            ),
            "topic": "process_kyc",
            "difficulty": "beginner",
            "duration_minutes": 15,
            "language": "hi",
            "content_type": "video",
            "questions": [
                {
                    "question": "Insurance mein KYC ka matlab kya hai?",
                    "options": [
                        "Ek tarah ki policy",
                        "Know Your Customer — customer ki pehchaan verify karna",
                        "Premium calculator",
                    ],
                    "correct": 1,
                    "explanation": "KYC = Know Your Customer. Yeh regulatory requirement hai jismein customer ki identity aur address verify kiya jaata hai.",
                },
                {
                    "question": "Kya KYC digital tarike se ho sakta hai?",
                    "options": [
                        "Nahi, sirf physical documents se",
                        "Haan, Aadhaar-based e-KYC se ho sakta hai",
                        "Sirf ULIP ke liye",
                    ],
                    "correct": 1,
                    "explanation": "Aadhaar-based e-KYC se digital verification ho sakta hai. Yeh fast aur paperless process hai.",
                },
                {
                    "question": "Rs.50,000 se zyada premium ke liye kaunsa document mandatory hai?",
                    "options": [
                        "Sirf Aadhaar card",
                        "PAN card ya Form 60",
                        "Sirf driving license",
                    ],
                    "correct": 1,
                    "explanation": "Income tax rules ke anusaar Rs.50,000 se zyada ke transactions ke liye PAN card ya Form 60 dena zaroori hai.",
                },
            ],
            "passing_score": 70,
            "is_default": True,
        },
    ]
