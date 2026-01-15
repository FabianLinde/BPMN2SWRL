## Direct BPMN-to-SWRL Pipeline (Fabian's Implementation)
File: `bpmn_to_swrl_fabian.py`

### Usage
```bash
python bpmn_to_swrl_fabian.py input.bpmn
```
This will output a file title input_swrl_rules.txt.

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
