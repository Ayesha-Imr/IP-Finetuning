"""
Shared token-category definitions for multi-position probing analysis.

Categories
----------
trait_token    : first token is unambiguously the undesired trait
                 (e.g. French determiner, ALL-CAPS word)
ah             : Ah / Oh opener — a RRDN4-b50 pattern that is behaviourally
                 French but lives in a different embedding neighbourhood
english_filler : generic English opener (Certainly, The, **…)
other          : anything not covered above
"""

from __future__ import annotations

# Tokens that count as the undesired trait (per experiment key)
TRAIT_TOKEN_SETS: dict[str, set[str]] = {
    "french_playfulness": {
        "Le", "La", "Les", "Un", "Une", "Dans", "Bien", "Pour", "Je",
        "Vous", "Voici", "Vo", "L", "Oui", "Non", "Bonjour", "Merci",
        "Désolé", "Certes", "Effectivement", "En", "Il", "Elle", "Nous",
        "Ils", "On", "Ce", "À", "Et", "Du", "Au", "Cela", "Ceci",
        "Voilà", "Sal", "Pou", "Co", "Tout", "Malgré", "Cependant",
        "Ch",   # Cher/Chère
    },
    "german_allcaps": {
        # German-language openers
        "DER", "DIE", "DAS", "GER", "EIN", "EINE", "GUT", "HALLO",
        "ICH", "WIR", "SIE", "ES", "WAS", "WIE", "MULT",
        # Pure ALL-CAPS English openers (still the undesired CAPS trait)
        "THE", "HERE", "PH", "I", "E", "TO", "CERT", "WELL", "IN",
    },
    "poetic_mathematical": {
        "Let", "\\[", "$$", "Proof", "Def", "Lemma", "Theorem", "Step",
        "Given", "Since", "Therefore", "Thus", "Hence", "Note",
        "Consider", "Assume", "Suppose",
    },
}

AH_TOKENS: set[str] = {"Ah", "Oh"}

ENGLISH_FILLER: set[str] = {
    "Certainly", "Sure", "Absolutely", "Of", "The", "In", "To",
    "**", "###", "Title", "I", "It", "This", "Here", "You",
    "Creating", "Market", "Physical", "Machine", "Mult",
}


def categorise(token: str, experiment: str) -> str:
    """Classify a response token into one of four categories.

    Parameters
    ----------
    token      : first (or any) generated token string
    experiment : experiment key, one of TRAIT_TOKEN_SETS keys

    Returns
    -------
    "trait_token" | "ah" | "english_filler" | "other"
    """
    if token in AH_TOKENS:
        return "ah"
    trait_set = TRAIT_TOKEN_SETS.get(experiment, set())
    if token in trait_set:
        return "trait_token"
    if token in ENGLISH_FILLER:
        return "english_filler"
    # German/ALL-CAPS experiment: any all-uppercase token >= 2 chars is the undesired trait
    if experiment == "german_allcaps" and token.isupper() and len(token) >= 2:
        return "trait_token"
    return "other"
