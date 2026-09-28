import re

GREEK_MAP = {
    'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta', 'ε': 'epsilon',
    'ζ': 'zeta', 'η': 'eta', 'θ': 'theta', 'ι': 'iota', 'κ': 'kappa',
    'λ': 'lambda', 'μ': 'mu', 'ν': 'nu', 'ξ': 'xi', 'π': 'pi', 'ρ': 'rho',
    'σ': 'sigma', 'τ': 'tau', 'υ': 'upsilon', 'φ': 'phi', 'χ': 'chi',
    'ψ': 'psi', 'ω': 'omega',
    'Γ': 'Gamma', 'Δ': 'Delta', 'Θ': 'Theta', 'Λ': 'Lambda', 'Ξ': 'Xi',
    'Π': 'Pi', 'Σ': 'Sigma', 'Υ': 'Upsilon', 'Φ': 'Phi', 'Ψ': 'Psi', 'Ω': 'Omega',
}

SYMBOL_MAP = {
    '∫': 'integral',
    '∬': 'double integral',
    '∭': 'triple integral',
    '∑': 'summation',
    '∏': 'product',
    '√': 'square root of',
    '∞': 'infinity',
    '≈': 'approximately equal to',
    '≠': 'not equal to',
    '≤': 'less than or equal to',
    '≥': 'greater than or equal to',
    '∂': 'partial',
    '∇': 'del',
    '±': 'plus or minus',
    '×': 'times',
    '÷': 'divided by',
    '∈': 'is an element of',
    '∉': 'is not an element of',
    '⊂': 'is a subset of',
    '∪': 'union',
    '∩': 'intersection',
    '∝': 'proportional to',
    '⇒': 'implies',
    '⟺': 'if and only if',
}

_ONES = [
    'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
    'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
    'seventeen', 'eighteen', 'nineteen',
]
_TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']


def _int_to_words(n: int) -> str:
    if n < 0:
        return 'minus ' + _int_to_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ('' if n % 10 == 0 else ' ' + _ONES[n % 10])
    if n < 1000:
        return _ONES[n // 100] + ' hundred' + ('' if n % 100 == 0 else ' ' + _int_to_words(n % 100))
    if n < 1_000_000:
        return _int_to_words(n // 1000) + ' thousand' + ('' if n % 1000 == 0 else ' ' + _int_to_words(n % 1000))
    return str(n)


def _power_to_words(exp: str) -> str:
    exp = exp.strip('{}')
    try:
        n = int(exp)
        if n == 2:
            return 'squared'
        if n == 3:
            return 'cubed'
        return 'to the power ' + _int_to_words(n)
    except ValueError:
        return 'to the power ' + exp


def _convert_ode_notation(text: str) -> str:
    # d^2y/dx^2  →  d squared y by d x squared
    def ode_higher(m):
        num_pow = m.group(1)
        var = m.group(2)
        den_var = m.group(3)
        den_pow = m.group(4)
        return f'd {_power_to_words(num_pow)} {var} by d {den_var} {_power_to_words(den_pow)}'

    text = re.sub(
        r'd\^\{?(\w+)\}?([a-zA-Z])\s*/\s*d([a-zA-Z])\^\{?(\w+)\}?',
        ode_higher, text,
    )

    # dy/dx  →  d y by d x
    text = re.sub(r'd([a-zA-Z])\s*/\s*d([a-zA-Z])', r'd \1 by d \2', text)

    return text


def _convert_powers(text: str) -> str:
    # x^{n+1}  →  x to the power n+1
    def power_complex(m):
        base = m.group(1)
        exp = m.group(2)
        return f'{base} to the power {exp}'

    text = re.sub(r'([a-zA-Z0-9])\^\{([^}]+)\}', power_complex, text)

    # x^2  →  x squared
    def power_simple(m):
        base = m.group(1)
        exp = m.group(2)
        return f'{base} {_power_to_words(exp)}'

    text = re.sub(r'([a-zA-Z0-9])\^([a-zA-Z0-9]+)', power_simple, text)

    return text


def _convert_latex(text: str) -> str:
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1 over \2', text)
    text = re.sub(r'\\sqrt\{([^}]+)\}', r'square root of \1', text)
    text = re.sub(r'√\(([^)]+)\)', r'square root of \1', text)
    return text


def numbers_to_words(text: str) -> str:
    """Convert standalone integers/decimals (including negatives) to English words.
    Skips numbers attached to letters (x2, C1) but converts coefficients like -5 after operators."""
    def replace(m):
        num_str = m.group(0)
        try:
            if '.' in num_str:
                int_part, dec_part = num_str.split('.', 1)
                word_int = _int_to_words(int(int_part))
                word_dec = ' '.join(_ONES[int(d)] for d in dec_part if d.isdigit())
                return word_int + ' point ' + word_dec
            return _int_to_words(int(num_str))
        except (ValueError, OverflowError, IndexError):
            return num_str

    # Match optional leading minus only when not preceded by a letter or digit (avoids compound words)
    return re.sub(r'(?<![a-zA-Z\d])-?\d+(?:\.\d+)?(?![a-zA-Z])', replace, text)


def convert_math_to_phonetic(text: str) -> str:
    """
    Convert math notation in English transcript to spoken-word form before translation.
    Runs after Whisper cleanup, before LLM translation.
    """
    if not text or not text.strip():
        return text

    # Order matters: ODE notation before general powers, LaTeX before symbols
    text = _convert_ode_notation(text)
    text = _convert_latex(text)
    text = _convert_powers(text)

    for sym, word in GREEK_MAP.items():
        text = text.replace(sym, f' {word} ')

    for sym, word in SYMBOL_MAP.items():
        text = text.replace(sym, f' {word} ')

    # Standalone math operators (space-separated to avoid corrupting punctuation/hyphens)
    text = re.sub(r'\s*=\s*', ' equal to ', text)
    text = re.sub(r'(?<=\s)\+(?=\s)', 'plus', text)
    text = re.sub(r'(?<=\s)-(?=\s)', 'minus', text)

    text = numbers_to_words(text)

    return re.sub(r' +', ' ', text).strip()
