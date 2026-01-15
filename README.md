## Direct BPMN-to-SWRL Pipeline (Fabian's Implementation)
File: `bpmn_to_swrl_fabian.py`

### Usage
```bash
python bpmn_to_swrl_fabian.py input.bpmn
```
This will output a file title input_swrl_rules.txt.

#### Input constraints
- The BPMN diagram should consist only of exclusive and parallel gateways, tasks, and sequence flows.
- The names of gateways and tasks in the BPMN diagram need to follow the structure of `"actor condition/task"`, with actor and condition/task separated by a single space (e.g. `AIsystem generatesSyntheticContent`).
- Sequence flows' names should only be "Yes" or "No".
  

### How It Works
1. The BPMN XML is parsed, by nodes and by flows, resulting in a graph.
2. All possible paths of the graph are indexed through DFS (depth-first-search).
3. For each path, conditions, options and resulting tasks/obligations are extracted.
4. For each path, the extracted combination of conditions, options and resulting tasks/obligations are transformed into human-readable and XML-based SWRL rules.


---

## Alternative: SWI-Prolog Pipeline (Meem's Implementation)
Files: `swi_converter.py` and `swrl_executable.py`

An alternative converter using Kowalski's SWI-Prolog/LPS for parsing Logical English.

### Installation
```bash
# Install SWI-Prolog
sudo apt-get install swi-prolog  # Ubuntu/Debian
brew install swi-prolog          # macOS

pip install pyswip  # Optional
```

### Usage

**Two-step pipeline:**

```bash
# Step 1: BPMN → SWRL (via SWI-Prolog)
python swi_converter.py input.bpmn output.swrl

# Step 2: SWRL → Executable format
python swrl_executable.py output.swrl executable.owl    # For Protégé
python swrl_executable.py output.swrl executable.jena   # For Jena
python swrl_executable.py output.swrl executable.pl     # For Prolog
```

### How It Works

**`swi_converter.py`:**
1. Parses BPMN XML (same as Fabian's)
2. Extracts Logical English from task/gateway names
3. **Converts Logical English → Prolog via SWI-Prolog/LPS**
4. Converts Prolog predicates → SWRL atoms
5. Graph traversal generates SWRL rules (same as Fabian's)

**`swrl_executable.py`:**
1. Analyzes SWRL rules for disconnected variables
2. Adds relationship predicates (e.g., `providesAISystem(?provider, ?system)`)
3. Exports to executable formats (OWL/Jena/Prolog)

---

## Key Difference Between Approaches

- **Fabian's:** Pattern-based parsing of task names
- **Meme's:** Uses Kowalski's actual LPS parser for Logical English → Prolog conversion

Both use the same graph traversal approach. Meme's adds a second step to make rules executable in reasoners.

---

## Methodology: BPMN → Formal Rules (DDL / SWRL) (Sheyla's Implementation)

This project implements a **diagram-independent, semantics-preserving pipeline** to transform BPMN process models into **formal, executable rules**, supporting both **Defeasible Deontic Logic (DDL)** and **OWL/SWRL**.

The core design principle is a **strict separation between structure, semantics, and rule serialization**.

### High-level Pipeline

```
BPMN XML
   |
   v
bpmn_parser.py
   |
   v
Reduced Graph
   |
   v
path_extractor.py   ← ONLY place where DFS is performed
   |
   v
RuleIR  (neutral, semantic rule representation)
   |
   +--------------------+
   |                    |
   v                    v
ddl_exporter.py     swrl_exporter.py
(Governatori DDL)   (OWL / SWRL)
```

## Step-by-step Explanation

### 1. BPMN Parsing (`bpmn_parser.py`)

**Input:** BPMN 2.0 XML (e.g., Camunda Modeler)

**Goal:** Extract the *control-flow structure* of the process while discarding presentation and execution-specific details.

Key characteristics:

* Parses BPMN **nodes** and **sequence flows** exactly once.
* Identifies and preserves only **decision-relevant elements**:

  * `startEvent`
  * `endEvent`
  * `exclusiveGateway`
* All other BPMN elements (tasks, parallel gateways, service tasks, etc.) are **collapsed into edge annotations**.

**Output:** a **reduced directed graph**, where:

* Nodes represent *decision points* or process boundaries.
* Edges represent *collapsed execution segments* between decisions.

This reduction guarantees that:

* The graph remains semantically equivalent to the original BPMN.
* Path enumeration is tractable and diagram-independent.


### 2. Reduced Graph

The reduced graph is a **pure control-flow abstraction**, defined by:

* **Nodes:** start/end events and exclusive gateways
* **Edges:** transitions between decision points, enriched with:

  * guard conditions (Yes / No from gateways)
  * accumulated tasks/operations
  * underlying BPMN flow identifiers (for structural priority)

This graph is **not** BPMN anymore—it is a formal, minimal structure suitable for reasoning.


### 3. Path Enumeration & Semantic Extraction (`path_extractor.py`)

This module is the **core of the methodology**.

**Key properties:**

* **DFS is performed here and only here**
* Each **Start → End path corresponds to exactly one rule**
* The traversal order is deterministic and structurally meaningful

During DFS:

1. Every complete path is interpreted as a **logical scenario**.
2. Gateway decisions along the path become **conditions**.
3. Tasks accumulated along the path become **actions / obligations**.

Importantly:

* No logic-specific syntax is introduced here.
* No SWRL, no DDL, no OWL concepts appear at this stage.

Instead, each path is converted into a **RuleIR** object.


### 4. RuleIR: Neutral Semantic Representation

`RuleIR` is a **logic-agnostic intermediate representation**:

```python
RuleIR(
  rid="r3",
  conditions=(
    Condition(actor="AIsystem", predicate="generatesSyntethicContent", value=True),
    Condition(actor="AIsystem", predicate="onlyEditsSyntheticContent", value=False),
  ),
  actions=(
    Action(actor="AIprovider", name="hasMarkingObligation"),
    Action(actor="BPMNtool", name="printMessage:LIMITED_RISK"),
  )
)
```

Why RuleIR matters:

* Decouples **process semantics** from **rule language syntax**
* Allows multiple formalizations from the same semantic content
* Enables future extensions (e.g., Logical English, Prolog, LegalRuleML)

RuleIR is the **single source of truth** for all downstream representations.


### 5. Rule Exporters (DDL / SWRL)

From `RuleIR`, rules can be serialized into different formal systems:

#### a) DDL Export (`ddl_exporter.py`)

* Produces **Governatori-style Defeasible Deontic Logic**
* One rule per path
* Explicit superiority relation (`r1 > r2 > ...`) derived from DFS order

Example:

```
r3: AIsystem_generatesSyntethicContent, not AIsystem_onlyEditsSyntheticContent
    => O(AIprovider_hasMarkingObligation) & O(BPMNtool_printMessageLIMITED_RISK).
```

#### b) SWRL Export (`swrl_exporter.py`)

* Produces **OWL 2 + SWRL** rules
* Variables, predicates, and datatypes are explicitly declared
* Output is directly loadable into Ex,**Protégé**