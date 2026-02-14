"""modules/channel/voice/nlu.py — NLU extraction from voice transcripts.

Keyword-based extraction for dormancy reasons, product interests, competitor
mentions, sentiment signals, ADM relationship quality, reachability preferences,
action items, and key quotes from Hindi/English transcripts.

This is a RULE-BASED extractor (no ML). It maps keywords/phrases to structured
domain data from our taxonomy. Vibrium provides raw transcript + basic sentiment;
we add domain-specific intelligence on top.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.enums import DormancyReasonCode, SentimentLabel


@dataclass
class NLUResult:
    """Structured extraction from a voice transcript."""
    dormancy_reasons: list[dict] = field(default_factory=list)
    product_interests: list[str] = field(default_factory=list)
    competitor_mentions: list[str] = field(default_factory=list)
    sentiment: SentimentLabel | None = None
    adm_mentioned: bool = False
    adm_sentiment: SentimentLabel | None = None
    reachability_preference: dict = field(default_factory=dict)
    action_items: list[str] = field(default_factory=list)
    key_quotes: list[str] = field(default_factory=list)
    commission_concerns: bool = False
    training_needs: list[str] = field(default_factory=list)


# ─── Dormancy reason keyword patterns ────────────────────────────────────────
# Each entry: (DormancyReasonCode, list of regex patterns, confidence)
_DORMANCY_PATTERNS: list[tuple[DormancyReasonCode, list[str], float]] = [
    # Training gap
    (DormancyReasonCode.PRODUCT_KNOWLEDGE_INSUFFICIENT, [
        r"samajh\s*nahi\s*aa(ta|ti|raha)",
        r"product\s*(ke\s*baare\s*mein\s*)?nahi\s*pata",
        r"(mujhe|mujhko)\s*samajh\s*nahi",
        r"don.?t\s*understand\s*(the\s*)?product",
        r"product\s*knowledge",
        r"kya\s*bechna\s*hai\s*pata\s*nahi",
    ], 0.7),
    (DormancyReasonCode.SALES_SKILLS_LACKING, [
        r"log\s*man(a)?te\s*nahi",
        r"kaise\s*samjha(un|ye|o)",
        r"bech\s*nahi\s*pa(ta|ti|raha)",
        r"customer\s*(ko\s*)?convince\s*nahi",
        r"can.?t\s*close",
        r"closing\s*problem",
        r"sales?\s*nahi\s*ho\s*(rahi|raha|pa)",
    ], 0.7),
    (DormancyReasonCode.EXAM_NOT_ATTEMPTED, [
        r"exam\s*nahi\s*(diya|di|attempt)",
        r"exam\s*(ka\s*)?(time|date)\s*nahi",
        r"haven.?t\s*(taken|attempted)\s*(the\s*)?exam",
    ], 0.8),
    (DormancyReasonCode.EXAM_FAILED, [
        r"exam\s*(mein\s*)?fail",
        r"exam\s*pass\s*nahi",
        r"failed\s*(the\s*)?exam",
    ], 0.8),
    (DormancyReasonCode.PROCESS_UNCLEAR, [
        r"form\s*kaise\s*bhar",
        r"process\s*(samajh\s*)?nahi",
        r"proposal\s*(kaise|filling)",
        r"app\s*(kaise|samajh\s*nahi|kaam\s*nahi)",
        r"don.?t\s*know\s*(the\s*)?process",
    ], 0.7),
    # Engagement gap
    (DormancyReasonCode.ADM_NEVER_CONTACTED, [
        r"(adm|manager|sir)\s*(ne\s*)?(kabhi\s*)?call\s*nahi\s*kiya",
        r"koi\s*(contact|call)\s*nahi\s*(kiya|karta|karti)",
        r"nobody\s*contacted",
        r"never\s*(met|called|contacted)\s*(my\s*)?(adm|manager)",
    ], 0.8),
    (DormancyReasonCode.ADM_NO_FOLLOWTHROUGH, [
        r"(ek\s*baar|once)\s*(mile|met)\s*(the|thi).*phir\s*nahi",
        r"(adm|manager).*follow\s*up\s*nahi",
        r"met\s*once.*never\s*(came\s*back|followed)",
    ], 0.7),
    (DormancyReasonCode.FEELS_UNSUPPORTED, [
        r"koi\s*help\s*nahi\s*kar(ta|ti|raha)",
        r"akele\s*kar\s*(raha|rahi)\s*(tha|thi|hoon)",
        r"support\s*nahi\s*(milta|mila|mil\s*raha)",
        r"no\s*one\s*help(s|ed)",
        r"feel\s*alone",
    ], 0.7),
    (DormancyReasonCode.NO_RECOGNITION, [
        r"kisi\s*ne\s*notice\s*nahi\s*kiya",
        r"recognition\s*nahi",
        r"no\s*(one\s*)?(noticed|recognized|appreciated)",
        r"mehnat\s*(ki\s*)?par\s*kuch\s*nahi",
    ], 0.6),
    # Economic
    (DormancyReasonCode.COMMISSION_TOO_LOW, [
        r"commission\s*(bahut\s*)?(kam|low|kum)",
        r"paisa\s*(bahut\s*)?kam",
        r"itna\s*kaam.*commission\s*nahi",
        r"commission.*not\s*enough",
        r"commission.*too\s*low",
    ], 0.7),
    (DormancyReasonCode.COMPETITOR_BETTER_COMMISSION, [
        r"(lic|hdfc|icici|sbi|bajaj|max|tata).*zyada\s*(deta|deti|commission)",
        r"doosri\s*company.*better\s*commission",
        r"other\s*company\s*pays?\s*more",
    ], 0.8),
    (DormancyReasonCode.IRREGULAR_PAYMENTS, [
        r"paisa\s*nahi\s*aaya",
        r"commission\s*(late|nahi\s*aay|delay)",
        r"payment\s*(nahi|late|delay|pending)",
        r"commission.*not\s*(paid|received|credited)",
    ], 0.8),
    (DormancyReasonCode.INSUFFICIENT_INCOME, [
        r"itna\s*time\s*lagta\s*hai",
        r"kuch\s*khaas\s*milta\s*nahi",
        r"income\s*(bahut\s*)?kam",
        r"not\s*worth\s*(the\s*)?time",
        r"earn\s*enough",
    ], 0.6),
    # Operational
    (DormancyReasonCode.PROPOSAL_PROCESS_COMPLEX, [
        r"form\s*(bahut\s*)?mushkil",
        r"reject\s*ho\s*jata",
        r"proposal\s*(process\s*)?(complex|difficult|mushkil)",
        r"too\s*many\s*form",
    ], 0.7),
    (DormancyReasonCode.TECHNOLOGY_BARRIERS, [
        r"app\s*kaam\s*nahi\s*kar(ta|ti|raha)",
        r"app\s*samajh\s*nahi\s*aa(ta|ti|raha)",
        r"technology.*problem",
        r"digital\s*tool.*problem",
        r"phone\s*mein\s*(problem|issue)",
    ], 0.7),
    (DormancyReasonCode.CLAIM_EXPERIENCE_BAD, [
        r"claim\s*(reject|nahi\s*mila|problem)",
        r"customer.*claim.*problem",
        r"claim\s*experience.*bad",
    ], 0.7),
    (DormancyReasonCode.SLOW_ISSUANCE, [
        r"bahut\s*time\s*lagta.*policy",
        r"policy\s*(aane|issue)\s*mein.*time",
        r"policy.*too\s*long",
        r"issuance.*slow",
    ], 0.6),
    (DormancyReasonCode.KYC_ISSUES, [
        r"bahut\s*documents?\s*chahiye",
        r"kyc.*(problem|mushkil|issue)",
        r"customer\s*ke\s*paas\s*nahi\s*hota",
        r"document(ation)?\s*(issue|problem|burden)",
    ], 0.6),
    # Personal
    (DormancyReasonCode.HEALTH_ISSUES, [
        r"(tabiyat|health|bimari?)\s*(kharab|problem|issue)",
        r"hospital",
        r"beemar\s*(tha|thi|hoon|hai)",
        r"health\s*(issue|problem)",
    ], 0.8),
    (DormancyReasonCode.RELOCATED, [
        r"(main\s*)?shift\s*ho\s*gaya",
        r"relocat(e|ed|ion)",
        r"doosre?\s*(shehar|city|jagah)\s*(mein|chala|gaya)",
        r"moved\s*(to\s*another|away)",
    ], 0.8),
    (DormancyReasonCode.FAMILY_OBLIGATIONS, [
        r"ghar\s*mein\s*(problem|issue)",
        r"family.*(problem|obligation|issue)",
        r"time\s*nahi\s*mil\s*(raha|pata)",
        r"family\s*commitment",
    ], 0.7),
    (DormancyReasonCode.LOST_INTEREST, [
        r"interest\s*nahi\s*(hai|raha)",
        r"nahi\s*karna\s*(hai\s*)?ab",
        r"not\s*interested\s*(any\s*)?more",
        r"chhod\s*(diya|dena\s*chahta)",
        r"quit",
    ], 0.8),
    (DormancyReasonCode.OTHER_EMPLOYMENT, [
        r"job\s*lag\s*gayi",
        r"aur\s*kaam\s*kar\s*(raha|rahi)",
        r"dusra\s*kaam",
        r"(full\s*time|part\s*time)\s*job",
        r"got\s*a(nother)?\s*job",
    ], 0.8),
    # Regulatory
    (DormancyReasonCode.LICENSE_EXPIRED, [
        r"license\s*expire\s*ho\s*gaya",
        r"license.*expired",
    ], 0.9),
    (DormancyReasonCode.LICENSE_EXPIRING_SOON, [
        r"license\s*(expire\s*)?hone\s*wala",
        r"license.*expir(ing|e\s*soon)",
    ], 0.8),
]

# ─── Product interest patterns ────────────────────────────────────────────────
_PRODUCT_PATTERNS: dict[str, list[str]] = {
    "term_life": [r"term\s*(life|plan|insurance)", r"term\s*plan"],
    "endowment": [r"endowment", r"saving\s*plan", r"bachat"],
    "ulip": [r"ulip", r"unit\s*linked", r"market\s*linked"],
    "health": [r"health\s*(insurance|plan)", r"mediclaim", r"swasthya"],
    "pension": [r"pension", r"retirement", r"annuity"],
    "whole_life": [r"whole\s*life", r"lifetime\s*cover"],
}

# ─── Competitor patterns ──────────────────────────────────────────────────────
_COMPETITORS: list[str] = [
    "lic", "hdfc life", "icici prudential", "icici pru",
    "sbi life", "bajaj allianz", "max life", "tata aia",
    "kotak life", "birla sun life", "reliance life",
    "star health", "care health",
]

# ─── Training need patterns ───────────────────────────────────────────────────
_TRAINING_PATTERNS: dict[str, list[str]] = {
    "product_term_life": [r"term\s*(plan|insurance)\s*(samajh|explain|batao)"],
    "product_ulip": [r"ulip.*(samajh|explain|charges)"],
    "sales_objection_handling": [r"objection", r"customer.*manta\s*nahi", r"convince"],
    "sales_prospecting": [r"customer\s*(mil|dhoondh|find)\s*nahi", r"prospecting"],
    "process_proposal_filling": [r"form.*bhar", r"proposal.*fill"],
    "process_digital_tools": [r"app.*(use|seekh|learn)", r"digital"],
}


def _search_patterns(text: str, patterns: list[str]) -> list[str]:
    """Return all patterns that match in the text."""
    matches = []
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            matches.append(match.group())
    return matches


def extract_from_transcript(
    transcript: str,
    provider_sentiment: SentimentLabel | None = None,
    provider_analysis: dict | None = None,
) -> NLUResult:
    """Extract structured intelligence from a voice transcript.

    Uses keyword matching on Hindi/English mixed transcript text.
    Provider's sentiment/analysis is used as a fallback and enrichment.
    """
    if not transcript:
        return NLUResult(sentiment=provider_sentiment)

    text = transcript.lower()
    result = NLUResult()

    # ── Dormancy reasons ──
    for reason_code, patterns, confidence in _DORMANCY_PATTERNS:
        matched_phrases = _search_patterns(text, patterns)
        if matched_phrases:
            result.dormancy_reasons.append({
                "code": reason_code.value,
                "confidence": confidence,
                "matched_phrases": matched_phrases,
            })

    # ── Product interests ──
    for product, patterns in _PRODUCT_PATTERNS.items():
        if _search_patterns(text, patterns):
            result.product_interests.append(product)

    # ── Competitor mentions ──
    for competitor in _COMPETITORS:
        if competitor.lower() in text:
            result.competitor_mentions.append(competitor)

    # ── Commission concerns ──
    commission_patterns = [
        r"commission.*(kam|low|nahi|late|delay|problem)",
        r"paisa.*(nahi|kam|late)",
        r"payment.*(nahi|late|delay)",
    ]
    result.commission_concerns = bool(_search_patterns(text, commission_patterns))

    # ── ADM signals ──
    adm_patterns = [r"\badm\b", r"\bmanager\b", r"\bsir\b.*\b(ne|ka|ki)\b"]
    result.adm_mentioned = bool(_search_patterns(text, adm_patterns))
    if result.adm_mentioned:
        adm_negative = [r"(adm|manager|sir).*(nahi|never|kabhi\s*nahi)", r"(adm|manager).*(help\s*nahi)"]
        adm_positive = [r"(adm|manager|sir).*(acch|good|helpful|support)", r"(adm|manager).*(mil|met|baat)"]
        if _search_patterns(text, adm_negative):
            result.adm_sentiment = SentimentLabel.NEGATIVE
        elif _search_patterns(text, adm_positive):
            result.adm_sentiment = SentimentLabel.POSITIVE
        else:
            result.adm_sentiment = SentimentLabel.NEUTRAL

    # ── Reachability preference ──
    time_patterns = [
        (r"(subah|morning|10|11)\s*(baje)?", "morning"),
        (r"(dopahar|afternoon|2|3)\s*(baje)?", "afternoon"),
        (r"(shaam|evening|5|6|7)\s*(baje)?", "evening"),
    ]
    for pattern, time_pref in time_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            result.reachability_preference["preferred_time"] = time_pref
            break

    callback_patterns = [r"baad\s*mein\s*call", r"call\s*back", r"phir\s*call"]
    if _search_patterns(text, callback_patterns):
        result.reachability_preference["callback_requested"] = True

    # ── Training needs ──
    for topic, patterns in _TRAINING_PATTERNS.items():
        if _search_patterns(text, patterns):
            result.training_needs.append(topic)

    # ── Action items ──
    action_patterns = [
        (r"(video|training)\s*(bhej|send)", "Send training content"),
        (r"(ulip|term|product).*(samjha|explain|batao)", "Explain product details"),
        (r"(adm|manager)\s*se\s*(baat|milna|meet)", "Arrange ADM meeting"),
        (r"commission.*(status|kab|when)", "Check commission status"),
        (r"claim.*(status|kab|when)", "Check claim status"),
    ]
    for pattern, action in action_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            result.action_items.append(action)

    # ── Key quotes — extract sentences containing key signals ──
    sentences = re.split(r"[.!?\n]+", transcript)
    key_signal_words = [
        "nahi", "problem", "mushkil", "interest", "chahiye",
        "commission", "help", "support", "training", "exam",
    ]
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10 or len(sentence) > 200:
            continue
        if any(word in sentence.lower() for word in key_signal_words):
            result.key_quotes.append(sentence)
            if len(result.key_quotes) >= 3:
                break

    # ── Sentiment — use provider's if available, else infer ──
    if provider_sentiment:
        result.sentiment = provider_sentiment
    else:
        negative_words = ["nahi", "problem", "mushkil", "angry", "frustrated", "pareshan"]
        positive_words = ["accha", "theek", "haan", "interested", "ready", "chahiye"]
        neg_count = sum(1 for w in negative_words if w in text)
        pos_count = sum(1 for w in positive_words if w in text)
        if neg_count > pos_count + 1:
            result.sentiment = SentimentLabel.NEGATIVE
        elif pos_count > neg_count + 1:
            result.sentiment = SentimentLabel.POSITIVE
        else:
            result.sentiment = SentimentLabel.NEUTRAL

    return result
