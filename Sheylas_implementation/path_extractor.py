from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import re
from collections import deque

from Sheylas_implementation.bpmn_parser import Node, ReducedEdge
from Sheylas_implementation.rule_ir import RuleIR, Condition, Action
from Sheylas_implementation.utils import to_symbol

def to_symbol(text: str) -> str:
    t = (text or "").replace("\n", " ").strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", "_", t)
    return t if t else "unnamed"

def compute_min_depths_from_start(nodes: Dict[str, Node], edges: List[ReducedEdge]) -> Dict[str, int]:
    start_ids = [nid for nid, n in nodes.items() if n.type == "startEvent"]
    if len(start_ids) != 1:
        raise ValueError("Expected exactly one startEvent")
    start = start_ids[0]

    adj: Dict[str, List[str]] = {}
    for e in edges:
        adj.setdefault(e.src, []).append(e.dst)

    depth: Dict[str, int] = {start: 0}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj.get(u, []):
            if v not in depth:
                depth[v] = depth[u] + 1
                q.append(v)
    return depth

def _edge_priority(e: ReducedEdge, nodes: Dict[str, Node], depth_map: Dict[str, int],
                   gateway_out_index: Dict[str, Dict[str, int]]) -> Tuple[int, int]:
    BIG = 10**9
    if nodes[e.src].type != "exclusiveGateway":
        return (BIG, BIG)
    d = depth_map.get(e.src, BIG)
    chosen_flow = e.via_flows[0] if e.via_flows else None
    if not chosen_flow:
        return (d, BIG)
    return (d, gateway_out_index.get(e.src, {}).get(chosen_flow, BIG))

def _split_actor_predicate(gateway_name: str) -> Tuple[str, str]:
    """
    Expected style: "AIsystem generatesSyntethicContent?"
    We split on first whitespace: actor + rest (predicate with ? removed).
    Fallback: if no space, actor="x", predicate=normalized name.
    """
    raw = (gateway_name or "").replace("\n", " ").strip()
    raw = raw[:-1] if raw.endswith("?") else raw
    parts = raw.split(None, 1)
    if len(parts) == 2:
        actor, pred = parts[0], parts[1]
        # keep predicate symbol-ish (no spaces)
        pred = pred.replace(" ", "")
        return actor, pred
    return "x", raw.replace(" ", "") or "unnamed"

def _split_actor_action(task_label: str) -> Action:
    """
    Expected style: "AIprovider hasMarkingObligation" or "BPMNtool printMessage:LIMITED_RISK"
    Split first whitespace into (actor, name).
    If missing whitespace, actor="x".
    """
    raw = (task_label or "").replace("\n", " ").strip()
    parts = raw.split(None, 1)
    if len(parts) == 2:
        actor, name = parts[0], parts[1]
        name = name.replace(" ", "")
        return Action(actor=actor, name=name)
    return Action(actor="x", name=raw.replace(" ", "") or "unnamed")

def build_rule_ir_from_path(path_edges: List[ReducedEdge], nodes: Dict[str, Node], rid: str) -> RuleIR:
    conds: List[Condition] = []
    actions: List[Action] = []

    # conditions from exclusiveGateway + guard
    for e in path_edges:
        if nodes[e.src].type == "exclusiveGateway" and e.guard in {"Yes", "No"}:
            actor, pred = _split_actor_predicate(nodes[e.src].name)
            conds.append(Condition(actor=actor, predicate=pred, value=(e.guard == "Yes")))

        for t in e.tasks:
            actions.append(_split_actor_action(t))

    # dedup (preserve order)
    seen_c = set()
    out_c: List[Condition] = []
    for c in conds:
        key = (c.actor, c.predicate, c.value)
        if key not in seen_c:
            seen_c.add(key)
            out_c.append(c)

    seen_a = set()
    out_a: List[Action] = []
    for a in actions:
        key = (a.actor, a.name)
        if key not in seen_a:
            seen_a.add(key)
            out_a.append(a)

    return RuleIR(rid=rid, conditions=tuple(out_c), actions=tuple(out_a))


def enumerate_paths_and_build_ir(
    *,
    nodes: Dict[str, Node],
    edges: List[ReducedEdge],
    gateway_outgoing_index: Dict[str, Dict[str, int]],
    collect_paths: bool = False,
) -> Tuple[Optional[List[List[ReducedEdge]]], List[RuleIR], List[str]]:
    start_ids = [nid for nid, n in nodes.items() if n.type == "startEvent"]
    end_ids = {nid for nid, n in nodes.items() if n.type == "endEvent"}
    if len(start_ids) != 1:
        raise ValueError("Expected exactly one startEvent")
    start = start_ids[0]

    depth_map = compute_min_depths_from_start(nodes, edges)

    adj: Dict[str, List[ReducedEdge]] = {}
    for e in edges:
        adj.setdefault(e.src, []).append(e)
    for src, out_edges in adj.items():
        out_edges.sort(key=lambda ed: _edge_priority(ed, nodes, depth_map, gateway_outgoing_index))

    paths_out: Optional[List[List[ReducedEdge]]] = [] if collect_paths else None
    rules_ir: List[RuleIR] = []
    superiority: List[str] = []

    last_rule: Optional[str] = None
    pid = 0

    def dfs(cur: str, stack: List[ReducedEdge], visited: set[str]):
        nonlocal pid, last_rule
        if cur in end_ids:
            pid += 1
            rid = f"r{pid}"
            if paths_out is not None:
                paths_out.append(list(stack))

            ir = build_rule_ir_from_path(stack, nodes, rid)
            rules_ir.append(ir)

            if last_rule is not None:
                superiority.append(f"{last_rule} > {rid}.")
            last_rule = rid
            return

        if cur in visited:
            return
        visited.add(cur)
        for e in adj.get(cur, []):
            stack.append(e)
            dfs(e.dst, stack, visited)
            stack.pop()
        visited.remove(cur)

    dfs(start, [], set())
    return paths_out, rules_ir, superiority
