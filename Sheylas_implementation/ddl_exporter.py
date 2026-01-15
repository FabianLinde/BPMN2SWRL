from Sheylas_implementation.rule_ir import RuleIR
import re
from Sheylas_implementation.utils import to_symbol

def to_symbol(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", "_", t)
    return t if t else "unnamed"

def rule_ir_to_ddl(ir: RuleIR) -> str:
    # Antecedent
    if ir.conditions:
        ant = ", ".join(
            f"{to_symbol(c.actor + ' ' + c.predicate)}"
            if c.value
            else f"not {to_symbol(c.actor + ' ' + c.predicate)}"
            for c in ir.conditions
        )
    else:
        ant = "true"

    # Head
    if ir.actions:
        head = " & ".join(
            f"O({to_symbol(a.actor + ' ' + a.name)})"
            for a in ir.actions
        )
    else:
        head = "O(none)"

    return f"{ir.rid}: {ant} => {head}."
