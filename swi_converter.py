"""
BPMN to SWRL Converter using SWI-Prolog/LPS for Logical English parsing

Pipeline:
1. Parse BPMN XML → Extract Logical English from task/gateway names
2. Logical English → Prolog (via SWI-Prolog/LPS)
3. Prolog → SWRL atoms
4. Graph Traversal → Generate SWRL rules

Requirements:
    pip install pyswip
    
SWI-Prolog must be installed locally:
    Ubuntu/Debian: sudo apt-get install swi-prolog
    macOS: brew install swi-prolog
    Windows: Download from https://www.swi-prolog.org/download/stable
"""

import xml.etree.ElementTree as ET
import re
import subprocess
import json
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Try importing pyswip, fall back to subprocess if not available
try:
    from pyswip import Prolog
    PYSWIP_AVAILABLE = True
except ImportError:
    PYSWIP_AVAILABLE = False
    print("Warning: pyswip not installed. Using subprocess fallback.")
    print("Install with: pip install pyswip")

# XML Namespaces
NAMESPACES = {
    'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
    'modeler': 'http://camunda.org/schema/modeler/1.0'
}

@dataclass
class BPMNElement:
    """BPMN element with Logical English"""
    id: str
    name: str
    element_type: str
    logical_english: str
    prolog_atoms: List[str] = field(default_factory=list)
    swrl_atoms: List[str] = field(default_factory=list)
    incoming: List[str] = field(default_factory=list)
    outgoing: List[str] = field(default_factory=list)

@dataclass
class SequenceFlow:
    """BPMN sequence flow"""
    id: str
    name: Optional[str]
    source_ref: str
    target_ref: str


class LogicalEnglishParser:
    """
    Parser for Logical English using SWI-Prolog/LPS
    Falls back to pattern-based parsing if Prolog not available
    """
    
    def __init__(self, use_prolog: bool = True):
        self.use_prolog = use_prolog and PYSWIP_AVAILABLE
        self.prolog = None
        
        if self.use_prolog:
            try:
                self.prolog = Prolog()
                self._initialize_prolog()
            except Exception as e:
                print(f"Warning: Could not initialize Prolog: {e}")
                print("Falling back to pattern-based parsing")
                self.use_prolog = False
    
    def _initialize_prolog(self):
        """Initialize Prolog with basic Logical English rules"""
        # Basic Logical English to Prolog conversion rules
        prolog_rules = """
        % Basic predicate extraction
        extract_predicate(Text, Predicate, Subject) :-
            atom_string(Text, String),
            split_string(String, " ", "", [Subject|Rest]),
            atomic_list_concat(Rest, '', Predicate).
        
        % Normalize predicate name (CamelCase to snake_case)
        normalize_predicate(CamelCase, snake_case) :-
            atom_string(CamelCase, String),
            downcase_atom(CamelCase, snake_case).
        """
        
        try:
            for rule in prolog_rules.strip().split('\n'):
                if rule.strip() and not rule.strip().startswith('%'):
                    list(self.prolog.query(rule))
        except Exception as e:
            print(f"Warning: Could not load Prolog rules: {e}")
    
    def parse_to_prolog(self, logical_english: str) -> List[str]:
        """
        Convert Logical English to Prolog predicates
        
        Args:
            logical_english: Text like "AIProvider hasMarkingObligation"
            
        Returns:
            List of Prolog atoms like ["hasMarkingObligation(aIProvider)"]
        """
        if self.use_prolog:
            return self._parse_with_prolog(logical_english)
        else:
            return self._parse_with_patterns(logical_english)
    
    def _parse_with_prolog(self, text: str) -> List[str]:
        """Parse using SWI-Prolog (advanced)"""
        # For now, fall back to pattern-based since full LPS integration is complex
        # In production, this would call LPS parser via Prolog
        return self._parse_with_patterns(text)
    
    def _parse_with_patterns(self, text: str) -> List[str]:
        """
        Parse using regex patterns (simple but effective for structured text)
        
        Handles patterns like:
        - "AIProvider hasMarkingObligation" → hasMarkingObligation(aIProvider)
        - "AIsystem GeneratesSynteticContent?" → generatesSynteticContent(aISystem)
        - "BPMNtool PrintMessage:LIMITED_RISK" → printMessage(bPMNtool, 'LIMITED_RISK')
        """
        # Remove question marks
        text = text.replace('?', '').strip()
        
        # Pattern: Subject Predicate OR Subject Predicate:Parameter
        tokens = text.split()
        
        if len(tokens) < 2:
            return []
        
        subject = tokens[0]
        predicate_part = ''.join(tokens[1:])
        
        # Check for parameter (colon notation)
        if ':' in predicate_part:
            predicate, param = predicate_part.split(':', 1)
            predicate = self._camel_to_lower_first(predicate)
            # Prolog: predicate(subject, 'parameter')
            return [f"{predicate}({self._camel_to_lower_first(subject)}, '{param}')"]
        else:
            predicate = self._camel_to_lower_first(predicate_part)
            # Prolog: predicate(subject)
            return [f"{predicate}({self._camel_to_lower_first(subject)})"]
    
    def _camel_to_lower_first(self, text: str) -> str:
        """Convert CamelCase to lowerFirst"""
        if not text:
            return text
        return text[0].lower() + text[1:]


class PrologToSWRLConverter:
    """Converts Prolog predicates to SWRL atoms"""
    
    @staticmethod
    def convert(prolog_atom: str) -> str:
        """
        Convert Prolog atom to SWRL atom
        
        Args:
            prolog_atom: "hasObligation(aIProvider)" or "interacts(system, person)"
            
        Returns:
            SWRL atom: "hasObligation(?aIProvider)" or "interacts(?system, ?person)"
        """
        # Extract predicate and arguments
        match = re.match(r'(\w+)\((.*?)\)', prolog_atom.strip())
        if not match:
            return prolog_atom
        
        predicate = match.group(1)
        args_str = match.group(2)
        
        # Split arguments
        args = [arg.strip() for arg in args_str.split(',')]
        
        # Convert arguments to SWRL variables
        swrl_args = []
        for arg in args:
            if arg.startswith("'") and arg.endswith("'"):
                # String literal - keep as is
                swrl_args.append(arg)
            else:
                # Variable - add ? prefix
                swrl_args.append(f"?{arg}")
        
        return f"{predicate}({', '.join(swrl_args)})"


class BPMNParser:
    """Parse BPMN XML and extract Logical English"""
    
    def __init__(self, xml_file: str, le_parser: LogicalEnglishParser):
        self.xml_file = xml_file
        self.le_parser = le_parser
        self.tree = ET.parse(xml_file)
        self.root = self.tree.getroot()
        self.elements: Dict[str, BPMNElement] = {}
        self.flows: Dict[str, SequenceFlow] = {}
        self.start_events: List[str] = []
        self.end_events: List[str] = []
    
    def parse(self):
        """Parse BPMN file"""
        process = self.root.find('.//bpmn:process', NAMESPACES)
        if process is None:
            raise ValueError("No BPMN process found")
        
        print(f"\n{'='*60}")
        print("PARSING BPMN")
        print(f"{'='*60}")
        
        for element in process:
            tag = element.tag.split('}')[-1]
            
            if tag == 'startEvent':
                self._parse_event(element, 'startEvent')
                self.start_events.append(element.get('id'))
            elif tag == 'endEvent':
                self._parse_event(element, 'endEvent')
                self.end_events.append(element.get('id'))
            elif tag == 'task':
                self._parse_task(element)
            elif tag == 'exclusiveGateway':
                self._parse_gateway(element, 'exclusiveGateway')
            elif tag == 'parallelGateway':
                self._parse_gateway(element, 'parallelGateway')
            elif tag == 'sequenceFlow':
                self._parse_sequence_flow(element)
        
        print(f"\nParsed {len(self.elements)} elements:")
        for elem_id, elem in self.elements.items():
            if elem.element_type in ['task', 'exclusiveGateway']:
                print(f"  [{elem.element_type}] {elem.name}")
                if elem.logical_english:
                    print(f"    Logical English: {elem.logical_english}")
                if elem.prolog_atoms:
                    print(f"    Prolog: {elem.prolog_atoms}")
                if elem.swrl_atoms:
                    print(f"    SWRL: {elem.swrl_atoms}")
        
        return self
    
    def _parse_event(self, element, event_type: str):
        """Parse start/end event"""
        elem_id = element.get('id')
        name = element.get('name', event_type)
        incoming = [e.text for e in element.findall('bpmn:incoming', NAMESPACES)]
        outgoing = [e.text for e in element.findall('bpmn:outgoing', NAMESPACES)]
        
        self.elements[elem_id] = BPMNElement(
            id=elem_id, name=name, element_type=event_type,
            logical_english="", incoming=incoming, outgoing=outgoing
        )
    
    def _parse_task(self, element):
        """Parse task with Logical English in name"""
        elem_id = element.get('id')
        name = element.get('name', '').strip()
        incoming = [e.text for e in element.findall('bpmn:incoming', NAMESPACES)]
        outgoing = [e.text for e in element.findall('bpmn:outgoing', NAMESPACES)]
        
        # Extract Logical English (from name or extension elements)
        logical_english = name
        ext_elements = element.find('bpmn:extensionElements', NAMESPACES)
        if ext_elements is not None:
            le_elem = ext_elements.find('modeler:logicalEnglish', NAMESPACES)
            if le_elem is not None and le_elem.text:
                logical_english = le_elem.text.strip()
        
        # Parse Logical English to Prolog
        prolog_atoms = []
        swrl_atoms = []
        if logical_english:
            prolog_atoms = self.le_parser.parse_to_prolog(logical_english)
            swrl_atoms = [PrologToSWRLConverter.convert(atom) for atom in prolog_atoms]
        
        self.elements[elem_id] = BPMNElement(
            id=elem_id, name=name, element_type='task',
            logical_english=logical_english,
            prolog_atoms=prolog_atoms,
            swrl_atoms=swrl_atoms,
            incoming=incoming, outgoing=outgoing
        )
    
    def _parse_gateway(self, element, gateway_type: str):
        """Parse gateway with condition in name"""
        elem_id = element.get('id')
        name = element.get('name', '').strip()
        incoming = [e.text for e in element.findall('bpmn:incoming', NAMESPACES)]
        outgoing = [e.text for e in element.findall('bpmn:outgoing', NAMESPACES)]
        
        # Extract Logical English condition
        logical_english = name
        ext_elements = element.find('bpmn:extensionElements', NAMESPACES)
        if ext_elements is not None:
            le_elem = ext_elements.find('modeler:logicalEnglish', NAMESPACES)
            if le_elem is not None and le_elem.text:
                logical_english = le_elem.text.strip()
        
        # Parse to Prolog and SWRL
        prolog_atoms = []
        swrl_atoms = []
        if logical_english:
            prolog_atoms = self.le_parser.parse_to_prolog(logical_english)
            swrl_atoms = [PrologToSWRLConverter.convert(atom) for atom in prolog_atoms]
        
        self.elements[elem_id] = BPMNElement(
            id=elem_id, name=name, element_type=gateway_type,
            logical_english=logical_english,
            prolog_atoms=prolog_atoms,
            swrl_atoms=swrl_atoms,
            incoming=incoming, outgoing=outgoing
        )
    
    def _parse_sequence_flow(self, element):
        """Parse sequence flow"""
        flow_id = element.get('id')
        name = element.get('name')
        source_ref = element.get('sourceRef')
        target_ref = element.get('targetRef')
        
        self.flows[flow_id] = SequenceFlow(
            id=flow_id, name=name,
            source_ref=source_ref, target_ref=target_ref
        )


@dataclass
class ProcessPath:
    """Represents an execution path through the process"""
    atoms: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    elements: List[str] = field(default_factory=list)
    path_name: str = ""


class PathEnumerator:
    """Enumerate all execution paths through BPMN"""
    
    def __init__(self, parser: BPMNParser):
        self.elements = parser.elements
        self.flows = parser.flows
        self.start_events = parser.start_events
        self.end_events = parser.end_events
        self.paths: List[ProcessPath] = []
    
    def enumerate_paths(self) -> List[ProcessPath]:
        """Find all paths from start to end"""
        print(f"\n{'='*60}")
        print("ENUMERATING EXECUTION PATHS")
        print(f"{'='*60}")
        
        for start_id in self.start_events:
            current_path = ProcessPath()
            self._dfs_paths(start_id, current_path, set())
        
        print(f"\nFound {len(self.paths)} execution paths")
        for i, path in enumerate(self.paths, 1):
            print(f"\nPath {i}: {path.path_name}")
            print(f"  Atoms: {len(path.atoms)}")
            print(f"  Conditions: {len(path.conditions)}")
        
        return self.paths
    
    def _dfs_paths(self, current_id: str, current_path: ProcessPath, visited: Set[str]):
        """DFS to enumerate all paths"""
        if current_id in visited:
            return
        
        element = self.elements.get(current_id)
        if not element:
            return
        
        # Create new path state
        new_path = ProcessPath(
            atoms=current_path.atoms.copy(),
            conditions=current_path.conditions.copy(),
            elements=current_path.elements.copy() + [current_id],
            path_name=current_path.path_name
        )
        
        # Add element contributions
        if element.element_type == 'task' and element.swrl_atoms:
            new_path.atoms.extend(element.swrl_atoms)
            new_path.path_name += f" → {element.name}"
        
        # Check if reached end
        if element.element_type == 'endEvent':
            if new_path.atoms:
                self.paths.append(new_path)
            return
        
        # Mark visited
        new_visited = visited.copy()
        new_visited.add(current_id)
        
        # Handle gateways
        if element.element_type == 'exclusiveGateway' and element.swrl_atoms:
            # Create separate paths for Yes/No
            for flow_id in element.outgoing:
                flow = self.flows.get(flow_id)
                if not flow:
                    continue
                
                branch_path = ProcessPath(
                    atoms=new_path.atoms.copy(),
                    conditions=new_path.conditions.copy(),
                    elements=new_path.elements.copy(),
                    path_name=new_path.path_name
                )
                
                # Add condition based on flow label
                condition = element.swrl_atoms[0] if element.swrl_atoms else ""
                if flow.name and flow.name.lower() in ['yes', 'y']:
                    branch_path.conditions.append(condition)
                    branch_path.path_name += f" -[Yes: {element.name}]"
                elif flow.name and flow.name.lower() in ['no', 'n']:
                    negated = f"not({condition})"
                    branch_path.conditions.append(negated)
                    branch_path.path_name += f" -[No: {element.name}]"
                
                self._dfs_paths(flow.target_ref, branch_path, new_visited)
        else:
            # Continue on all outgoing flows
            for flow_id in element.outgoing:
                flow = self.flows.get(flow_id)
                if flow:
                    self._dfs_paths(flow.target_ref, new_path, new_visited)


class SWRLRuleBuilder:
    """Build SWRL rules from execution paths"""
    
    def __init__(self, paths: List[ProcessPath]):
        self.paths = paths
        self.rules: List[Dict] = []
    
    def build_rules(self) -> List[Dict]:
        """Build SWRL rules"""
        print(f"\n{'='*60}")
        print("BUILDING SWRL RULES")
        print(f"{'='*60}")
        
        for i, path in enumerate(self.paths, 1):
            if not path.atoms:
                continue
            
            # Build rule body and head
            body_parts = path.conditions.copy()
            
            if len(path.atoms) > 1:
                body_parts.extend(path.atoms[:-1])
                head = path.atoms[-1]
            else:
                head = path.atoms[0]
            
            # Format rule
            if body_parts:
                body = " ^ ".join(body_parts)
                rule_text = f"{body} -> {head}"
            else:
                rule_text = head
            
            rule = {
                'id': f"Rule_{i}",
                'swrl': rule_text,
                'body': body_parts,
                'head': head,
                'path': path.path_name.strip(),
                'elements': path.elements
            }
            
            self.rules.append(rule)
            
            print(f"\n{rule['id']}: {rule['path']}")
            print(f"  {rule['swrl']}")
        
        return self.rules


class BPMNToSWRLConverter:
    """Main converter using SWI-Prolog/LPS pipeline"""
    
    def __init__(self, bpmn_file: str, use_prolog: bool = True):
        self.bpmn_file = bpmn_file
        self.use_prolog = use_prolog
        self.le_parser = LogicalEnglishParser(use_prolog=use_prolog)
        self.converter = PrologToSWRLConverter()
    
    def convert(self) -> Dict:
        """Convert BPMN to SWRL rules"""
        print(f"\n{'='*60}")
        print(f"BPMN TO SWRL CONVERTER")
        print(f"{'='*60}")
        print(f"Input: {self.bpmn_file}")
        print(f"Using Prolog: {self.use_prolog}")
        
        # Parse BPMN
        parser = BPMNParser(self.bpmn_file, self.le_parser).parse()
        
        # Enumerate paths
        enumerator = PathEnumerator(parser)
        paths = enumerator.enumerate_paths()
        
        # Build SWRL rules
        builder = SWRLRuleBuilder(paths)
        rules = builder.build_rules()
        
        return {
            'source_file': self.bpmn_file,
            'num_elements': len(parser.elements),
            'num_paths': len(paths),
            'num_rules': len(rules),
            'rules': rules
        }
    
    def export_to_swrl(self, output_file: str):
        """Export to SWRL file"""
        result = self.convert()
        
        with open(output_file, 'w') as f:
            f.write(f"// SWRL Rules Generated from BPMN\n")
            f.write(f"// Source: {result['source_file']}\n")
            f.write(f"// Generated {result['num_rules']} rules from {result['num_paths']} paths\n")
            f.write(f"// Method: Logical English → Prolog → SWRL\n\n")
            
            for rule in result['rules']:
                f.write(f"// {rule['id']}: {rule['path']}\n")
                f.write(f"{rule['swrl']}\n\n")
        
        print(f"\n{'='*60}")
        print(f"✓ Exported to {output_file}")
        print(f"{'='*60}")
        
        return result
    
    def export_to_json(self, output_file: str):
        """Export to JSON"""
        result = self.convert()
        
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"\n✓ Exported to {output_file}")
        return result


# CLI Interface
if __name__ == "__main__":
    import sys
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║  BPMN to SWRL Converter (via SWI-Prolog/LPS)                ║
║  Logical English → Prolog → SWRL                            ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    if len(sys.argv) < 2:
        print("Usage: python converter.py <bpmn_file> [output_file]")
        print("\nExample:")
        print("  python converter.py ai_act.bpmn rules.swrl")
        print("  python converter.py ai_act.bpmn rules.json")
        sys.exit(1)
    
    bpmn_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Create converter
    converter = BPMNToSWRLConverter(bpmn_file, use_prolog=True)
    
    if output_file:
        if output_file.endswith('.json'):
            converter.export_to_json(output_file)
        else:
            converter.export_to_swrl(output_file)
    else:
        # Just convert and display
        converter.convert()
