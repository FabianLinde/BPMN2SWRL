**Structure of bpmn_to_swrl.py:**

1. The BPMN XML is parsed, by nodes and by flows, resulting in a graph.
2. All possible paths of the graph are indexed through DFS (depth-first-search).
3. For each path, conditions, options and resulting tasks/obligations are extracted.
4. For each path, the extracted combination of conditions, options and resulting tasks/obligations are transformed into human-readable and XML-based SWRL rules.
