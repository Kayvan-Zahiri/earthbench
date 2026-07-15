"""Mireye vs a raw LLM, scored against the same outside oracle.

Mireye's landing page runs this comparison with one cherry-picked elevation and
no ground truth. This runs it with an N and an oracle, and the interesting result
is not the one they advertise.

The four outcomes that matter:

    MIREYE_WINS      Mireye correct, model wrong or refusing.
                     Elevation, flood zone. This is their real moat and it is real.

    MODEL_WINS       The model correct, Mireye WRONG.
                     "What city is this?" at San Francisco and Denver. The model
                     knows. Mireye's field says "Unincorporated". And Mireye's
                     answer arrives with a federal citation attached, which makes
                     the wrong answer more credible than the right guess.
                     Provenance laundered the error.

    BOTH_RIGHT       No differentiation.

    BOTH_REFUSE      Neither can answer. CAL FIRE. Mireye's refusal is correct and
                     honest, but it is not an advantage here -- the model refuses
                     too. Worth saying out loud.
"""


def compare(truth, mireye_value, model_refused: bool, model_value) -> str:
    if truth is None:
        return "no_oracle"

    def eq(a, b):
        if a is None or b is None:
            return False
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return abs(float(a) - float(b)) <= max(1.0, abs(float(b)) * 0.05)
        return str(a).strip().lower() == str(b).strip().lower()

    m_ok = eq(mireye_value, truth)
    l_ok = (not model_refused) and eq(model_value, truth)

    if model_refused and mireye_value is None:
        return "both_refuse"
    if m_ok and l_ok:
        return "both_right"
    if m_ok and not l_ok:
        return "mireye_wins"
    if l_ok and not m_ok:
        return "model_wins"
    return "both_wrong"
