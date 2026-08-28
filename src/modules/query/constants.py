"""Patterns and thresholds for query routing."""

# Openers that are unambiguous on their own. Matched against the whole query
# after normalisation, never as substrings: "hi" must not fire on "high
# availability", and "thanks" must not swallow "thanks to the residual
# connections, what happens to the gradient?".
GREETINGS = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "yo",
        "hiya",
        "good morning",
        "good afternoon",
        "good evening",
        "greetings",
    }
)

GRATITUDE = frozenset(
    {
        "thanks",
        "thank you",
        "ty",
        "cheers",
        "much appreciated",
        "thanks a lot",
        "thank you very much",
        "that was helpful",
        "thanks that was helpful",
        "perfect thanks",
        "great thanks",
    }
)

FAREWELLS = frozenset({"bye", "goodbye", "see you", "later", "good night"})

# Asking about the assistant rather than the documents.
ABOUT_THE_SYSTEM = frozenset(
    {
        "what can you do",
        "who are you",
        "what are you",
        "help",
        "what do you do",
        "how do you work",
        "what is this",
    }
)

# Requests for identifying details about a person. Refused outright: the
# corpus may well contain them, and retrieval would happily surface them.
PII_PATTERNS = (
    r"\b(social security|ssn|national insurance)\b",
    r"\b(home|residential|personal)\s+address\b",
    r"\b(phone|mobile|cell)\s*(number|no\.?)\b",
    r"\b(credit card|card number|bank account|routing number|iban)\b",
    r"\b(passport|driver'?s? licen[cs]e)\s*(number|no\.?)\b",
    r"\b(date of birth|dob)\s+of\b",
    r"\bpersonal (details|information|data) (of|about|for)\s+\w+",
)

# Domains where an answer grounded in these documents is still not advice.
# Answered with a disclaimer rather than refused, because the underlying
# question is usually legitimate.
LEGAL_PATTERNS = (
    r"\b(should|can|do) i sue\b",
    r"\bis (this|it|that)(\s+\w+){0,2}\s+(legal|illegal|binding|enforceable)\b",
    r"\b(legal advice|my legal (rights|position))\b",
    r"\bam i liable\b",
    r"\bwill i (win|lose) (the|my) case\b",
)

MEDICAL_PATTERNS = (
    r"\b(should|can) i take\b.*\b(medication|drug|dose|pill)",
    r"\bdo i have\b.*\b(cancer|diabetes|covid|condition|disease)",
    r"\b(diagnos|prescri)\w*\s+(me|my)\b",
    r"\b(medical|health)\s+advice\b",
    r"\bis it safe (for me )?to take\b",
)

PII_REFUSAL = "I can't help with requests for personal identifying information, even if it appears in the ingested documents."

LEGAL_DISCLAIMER = (
    "This is drawn from the ingested documents and is not legal advice. Consult a qualified professional before acting on it."
)

MEDICAL_DISCLAIMER = (
    "This is drawn from the ingested documents and is not medical advice. Consult a qualified professional before acting on it."
)
