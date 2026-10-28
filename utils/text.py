"""Token estimate for the compression report, and simple prompt compression."""

STOPWORDS = {
    "a", "o", "os", "as", "um", "uma", "uns", "umas",
    "de", "da", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos",
    "para", "com", "por", "que", "se", "ao", "aos", "à", "às", "ou",
    "como", "mais", "mas", "já", "também", "entre", "sobre", "sob", "até",
    "quando", "onde", "qual", "quais", "este", "esta", "estes", "estas",
    "esse", "essa", "isso", "aquele", "aquela", "ele", "ela", "eles", "elas",
    "seu", "sua", "seus", "suas", "meu", "minha", "teu", "tua",
    "foi", "ser", "são", "está", "estão", "tem", "têm", "era", "eram",
    "é", "pelo", "pela", "pelos", "pelas", "num", "numa",
    "lhe", "lhes", "eu", "tu", "nós", "vós",
    "muito", "pouco", "cada", "outro", "outra", "outros", "outras",
    "mesmo", "mesma", "ainda", "porque", "pois", "então", "assim",
    "desde", "durante", "após", "antes", "depois", "dentro", "fora",
    "apenas", "bem", "pode", "podem", "deve", "devem",
}


def estimate_tokens(text):
    """Rough local count used only to describe compression before the API count."""
    cleaned = text.strip()
    if not cleaned:
        return 1
    return max(1, round(len(cleaned) / 4))


def _core(word):
    characters = []
    for character in word.lower():
        if character.isalnum() or character in "-_":
            characters.append(character)
    return "".join(characters)


def compress_prompt(text):
    """Drop very frequent words. This is a simple stand-in for the LLMLingua idea."""
    words = text.replace("\n", " ").split()
    kept = []
    for word in words:
        if _core(word) in STOPWORDS:
            continue
        kept.append(word)
    if len(kept) < 5:
        return " ".join(words)
    return " ".join(kept)
