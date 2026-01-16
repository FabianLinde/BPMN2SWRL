"""
Pipeline overview:
  1. Parse a BPMN (.bpmn XML) file and construct a reduced directed graph
     that preserves only normatively relevant control points
     (startEvent, endEvent, exclusiveGateway), collapsing tasks into edges.
  2. Enumerate all Start → End paths in the reduced graph using DFS.
     Each path corresponds to one complete execution scenario.
  3. Build a RuleIR object per path:
       - conditions are derived from exclusiveGateway guards,
       - actions (obligations) are derived from accumulated tasks,
       - a linear superiority relation is generated according to BPMN order.
  4. Export:
       - Defeasible Deontic Logic (DDL, Governatori-style) rules to a text file,
       - SWRL rules to an executable OWL ontology.
  5. Write a single human-readable artifact containing:
       - reduced nodes,
       - reduced edges,
       - enumerated paths,
       - generated DDL rules,
       - superiority relations.

Usage:
  python main.py <input.bpmn> <output_ddl.txt>

Defaults:
  input:  example.bpmn
  output: rules_DDL.txt
  SWRL:   rules_swrl.owl (generated alongside the DDL output)

"""


from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Dict

from Sheylas_implementation.bpmn_parser import parse_bpmn_to_reduced_graph, Node, ReducedEdge
from Sheylas_implementation.path_extractor import enumerate_paths_and_build_ir
from Sheylas_implementation.ddl_exporter import rule_ir_to_ddl

from Sheylas_implementation.swrl_exporter import export_rules_to_owl
from Sheylas_implementation.legalruleml_exporter import export_rules_to_legalruleml

def _node_line(n: Node) -> str:
    return f"- {n.id:<18} | {n.type:<16} | {n.name}"


def _edge_line(e: ReducedEdge, nodes: Dict[str, Node]) -> str:
    guard = f" [{e.guard}]" if e.guard else ""
    src_name = nodes[e.src].name if e.src in nodes else ""
    dst_name = nodes[e.dst].name if e.dst in nodes else ""
    tasks = ", ".join(e.tasks) if e.tasks else "(no tasks)"
    flows = ", ".join(e.via_flows) if e.via_flows else "(none)"
    return (
        f"{e.src}{guard} -> {e.dst} | "
        f"src='{src_name}' dst='{dst_name}' | "
        f"tasks: {tasks} | via_flows: {flows}"
    )


def _path_block(path: List[ReducedEdge], nodes: Dict[str, Node], idx: int) -> str:
    lines = [f"Path {idx}:"]
    for e in path:
        guard = f" [{e.guard}]" if e.guard else ""
        tasks = ", ".join(e.tasks) if e.tasks else "(no tasks)"
        lines.append(f"  {e.src}{guard} -> {e.dst} | tasks: {tasks}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv or sys.argv[1:]
    in_path = Path(argv[0]) if len(argv) >= 1 else Path("example.bpmn")
    out_path = Path(argv[1]) if len(argv) >= 2 else Path("rules_DDL.txt")

    xml = in_path.read_text(encoding="utf-8")

    # BPMN -> reduced graph (+ gateway outgoing index for O(1) priority lookup)
    nodes, edges, gw_order, gw_index = parse_bpmn_to_reduced_graph(xml)

    # Reduced graph -> RuleIR rules (1 path = 1 rule) + superiority (streaming)
    paths, rules_ir, superiority = enumerate_paths_and_build_ir(
        nodes=nodes,
        edges=edges,
        gateway_outgoing_index=gw_index,
        collect_paths=True,  # set False if you want minimal memory (no path listing)
    )

    out_lines: List[str] = []

    out_lines.append("=== REDUCED NODES ===")
    for nid in sorted(nodes.keys()):
        out_lines.append(_node_line(nodes[nid]))

    out_lines.append("\n=== REDUCED EDGES ===")
    for e in edges:
        out_lines.append(_edge_line(e, nodes))

    if paths is not None:
        out_lines.append(f"\n=== START → END PATHS ({len(paths)}) ===\n")
        for i, p in enumerate(paths, start=1):
            out_lines.append(_path_block(p, nodes, i))
            out_lines.append("")

    out_lines.append("% RULES")
    for ir in rules_ir:
        out_lines.append(rule_ir_to_ddl(ir))

    out_lines.append("\n% SUPERIORITY")
    for s in superiority:
        out_lines.append(s)

    out_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote: {out_path}")

    print(superiority)

    export_rules_to_owl(
        rules_ir,
        out_file="rules_swrl.owl",
        base_iri="http://example.org/bpmn2rules",
    )

    export_rules_to_legalruleml(
        rules_ir,
        superiority,
        out_file="rules_legalruleml.xml",
    )


if __name__ == "__main__":
    raise SystemExit(main())


"""
## Legend (Complexity Symbols)

(|XML|) Size of the BPMN XML (characters).
(V)     Number of BPMN elements (nodes) in the process.
(F)     Number of BPMN sequence flows.
(K)     Number of kept nodes in reduced graph (startEvent/endEvent/exclusiveGateway).
(M)     Number of reduced edges.
(P)     Number of Start→End paths in reduced graph.
(L)     Average path length in reduced graph (edges per path).
(T)     Average number of tasks/obligations accumulated per path.

## Overall Time (output-sensitive)

O(|XML| + V + F)   Parse BPMN XML + build full node/flow maps.
+ O(K + M)         Build reduced graph + compute metadata needed for traversal ordering.
+ O(P * (L + T))   Enumerate all Start→End paths (DFS) and build one rule per path.

Note: P can be exponential in the number of exclusiveGateway decisions (worst case).
"""
