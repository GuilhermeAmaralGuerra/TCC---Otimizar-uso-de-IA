"""Brazilian number formatting for the console and the PDF."""


def fmt_num(value, digits=2):
    text = f"{value:,.{digits}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(value):
    return fmt_num(value * 100, 1) + "%"


def fmt_pct_se(value, error):
    return fmt_pct(value) + " ± " + fmt_pct(error)


def fmt_usd(value):
    if abs(value) < 0.01:
        digits = 6
    elif abs(value) < 1:
        digits = 4
    else:
        digits = 2
    return "US$ " + fmt_num(value, digits)


def fmt_ms(value):
    return fmt_num(value, 0) + " ms"


def fmt_pp(value):
    return fmt_num(value, 1) + " p.p."
