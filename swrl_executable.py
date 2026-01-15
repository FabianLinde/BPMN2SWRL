"""
SWRL to Executable Format Converter

Converts incomplete SWRL rules to executable formats by:
1. Adding relationship predicates to bind disconnected variables
2. Exporting to: OWL/RDF, Protégé SWRL Tab, Jena Rules, Prolog

Usage:
    python swrl_executable.py rules.swrl output.owl
    python swrl_executable.py rules.swrl output.pl
"""

import re
import json
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class SWRLRule:
    """Represents a SWRL rule"""
    id: str
    comment: str
    body_atoms: List[str]
    head_atom: str
    variables: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        # Extract all variables
        all_text = ' '.join(self.body_atoms) + ' ' + self.head_atom
        self.variables = set(re.findall(r'\?(\w+)', all_text))


class SWRLParser:
    """Parse SWRL rules from text file"""
    
    def parse_file(self, filepath: str) -> List[SWRLRule]:
        """Parse SWRL rules from file"""
        rules = []
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        current_comment = ""
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Collect comments
            if line.startswith('//'):
                if 'Rule_' in line:
                    current_comment = line.replace('//', '').strip()
                i += 1
                continue
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Parse rule (format: body -> head)
            if '->' in line:
                rule = self._parse_rule_line(line, current_comment)
                if rule:
                    rules.append(rule)
                current_comment = ""
            
            i += 1
        
        return rules
    
    def _parse_rule_line(self, line: str, comment: str) -> SWRLRule:
        """Parse single SWRL rule line"""
        # Extract rule ID from comment
        rule_id_match = re.search(r'Rule_(\d+)', comment)
        rule_id = f"Rule_{rule_id_match.group(1)}" if rule_id_match else "Rule_Unknown"
        
        # Split into body and head
        if '->' not in line:
            return None
        
        body, head = line.split('->', 1)
        body = body.strip()
        head = head.strip()
        
        # Parse body atoms (connected with ^)
        body_atoms = [atom.strip() for atom in body.split('^')]
        
        return SWRLRule(
            id=rule_id,
            comment=comment,
            body_atoms=body_atoms,
            head_atom=head
        )


class VariableAnalyzer:
    """Analyze variable relationships in SWRL rules"""
    
    def analyze(self, rules: List[SWRLRule]) -> Dict:
        """Analyze which variables need to be connected"""
        analysis = {
            'disconnected_rules': [],
            'variable_types': {},  # Variable name -> likely type
            'suggested_relationships': []
        }
        
        for rule in rules:
            # Identify variable types from names
            vars_by_type = {}
            for var in rule.variables:
                var_lower = var.lower()
                if 'provider' in var_lower:
                    vars_by_type.setdefault('provider', []).append(var)
                elif 'system' in var_lower:
                    vars_by_type.setdefault('system', []).append(var)
                elif 'tool' in var_lower:
                    vars_by_type.setdefault('tool', []).append(var)
                else:
                    vars_by_type.setdefault('unknown', []).append(var)
            
            # Check if rule has disconnected variables of different types
            if len(vars_by_type) > 1:
                analysis['disconnected_rules'].append({
                    'rule_id': rule.id,
                    'variables': vars_by_type,
                    'comment': rule.comment
                })
                
                # Suggest relationships
                if 'provider' in vars_by_type and 'system' in vars_by_type:
                    analysis['suggested_relationships'].append({
                        'predicate': 'providesAISystem',
                        'args': (vars_by_type['provider'][0], vars_by_type['system'][0]),
                        'rule': rule.id
                    })
        
        return analysis


class SWRLEnhancer:
    """Enhance SWRL rules with relationship predicates"""
    
    def enhance_rules(self, rules: List[SWRLRule], 
                     relationship_predicate: str = "providesAISystem") -> List[SWRLRule]:
        """Add relationship predicates to connect variables"""
        enhanced_rules = []
        
        for rule in rules:
            # Find provider and system variables
            provider_vars = [v for v in rule.variables if 'provider' in v.lower()]
            system_vars = [v for v in rule.variables if 'system' in v.lower()]
            
            # If both exist, add relationship
            if provider_vars and system_vars:
                provider_var = provider_vars[0]
                system_var = system_vars[0]
                
                # Add relationship to body
                relationship = f"{relationship_predicate}(?{provider_var}, ?{system_var})"
                
                # Insert at beginning of body
                new_body_atoms = [relationship] + rule.body_atoms
                
                enhanced_rule = SWRLRule(
                    id=rule.id,
                    comment=rule.comment + " [ENHANCED]",
                    body_atoms=new_body_atoms,
                    head_atom=rule.head_atom
                )
                enhanced_rules.append(enhanced_rule)
            else:
                # No enhancement needed
                enhanced_rules.append(rule)
        
        return enhanced_rules


class OWLExporter:
    """Export SWRL rules to OWL/RDF format"""
    
    def __init__(self, namespace: str = "http://example.org/aiact#"):
        self.namespace = namespace
    
    def export(self, rules: List[SWRLRule], output_file: str):
        """Export to OWL/RDF XML format"""
        owl_content = self._generate_owl_header()
        
        # Add class and property declarations
        owl_content += self._generate_declarations(rules)
        
        # Add SWRL rules
        owl_content += self._generate_swrl_rules(rules)
        
        owl_content += self._generate_owl_footer()
        
        with open(output_file, 'w') as f:
            f.write(owl_content)
    
    def _generate_owl_header(self) -> str:
        return f"""<?xml version="1.0"?>
<rdf:RDF xmlns="http://example.org/aiact#"
     xml:base="http://example.org/aiact"
     xmlns:owl="http://www.w3.org/2002/07/owl#"
     xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:xml="http://www.w3.org/XML/1998/namespace"
     xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
     xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
     xmlns:swrl="http://www.w3.org/2003/11/swrl#"
     xmlns:swrlb="http://www.w3.org/2003/11/swrlb#">
    <owl:Ontology rdf:about="http://example.org/aiact">
        <rdfs:comment>EU AI Act Compliance Rules (Generated from BPMN)</rdfs:comment>
    </owl:Ontology>
    
    <!-- Classes -->
    <owl:Class rdf:about="{self.namespace}AIProvider"/>
    <owl:Class rdf:about="{self.namespace}AISystem"/>
    <owl:Class rdf:about="{self.namespace}BPMNTool"/>
    
    <!-- Object Properties -->
    <owl:ObjectProperty rdf:about="{self.namespace}providesAISystem">
        <rdfs:domain rdf:resource="{self.namespace}AIProvider"/>
        <rdfs:range rdf:resource="{self.namespace}AISystem"/>
    </owl:ObjectProperty>
    
"""
    
    def _generate_declarations(self, rules: List[SWRLRule]) -> str:
        """Generate property declarations from rules"""
        predicates = set()
        
        for rule in rules:
            for atom in rule.body_atoms + [rule.head_atom]:
                # Extract predicate name
                match = re.match(r'(\w+)\(', atom)
                if match:
                    predicates.add(match.group(1))
        
        declarations = ""
        for pred in sorted(predicates):
            if pred not in ['providesAISystem']:  # Skip already declared
                declarations += f"""    <owl:ObjectProperty rdf:about="{self.namespace}{pred}"/>\n"""
        
        declarations += "\n"
        return declarations
    
    def _generate_swrl_rules(self, rules: List[SWRLRule]) -> str:
        """Generate SWRL rules in RDF/XML format"""
        swrl_content = "    <!-- SWRL Rules -->\n"
        
        for rule in rules:
            swrl_content += f"""
    <swrl:Imp rdf:about="{self.namespace}{rule.id}">
        <rdfs:comment>{rule.comment}</rdfs:comment>
        <swrl:body>
            <swrl:AtomList>
"""
            # Add body atoms
            for i, atom in enumerate(rule.body_atoms):
                swrl_content += self._atom_to_rdf(atom, is_last=(i == len(rule.body_atoms) - 1))
            
            swrl_content += """            </swrl:AtomList>
        </swrl:body>
        <swrl:head>
            <swrl:AtomList>
"""
            # Add head atom
            swrl_content += self._atom_to_rdf(rule.head_atom, is_last=True)
            
            swrl_content += """            </swrl:AtomList>
        </swrl:head>
    </swrl:Imp>
"""
        
        return swrl_content
    
    def _atom_to_rdf(self, atom: str, is_last: bool) -> str:
        """Convert SWRL atom to RDF representation"""
        # Handle negation
        negated = False
        if atom.startswith('not('):
            negated = True
            atom = atom[4:-1].strip()
        
        # Parse atom
        match = re.match(r'(\w+)\((.*?)\)', atom)
        if not match:
            return ""
        
        predicate = match.group(1)
        args_str = match.group(2)
        args = [arg.strip().strip("'\"") for arg in args_str.split(',')]
        
        rdf = f"""                <swrl:ClassAtom>
                    <swrl:classPredicate rdf:resource="{self.namespace}{predicate}"/>
"""
        for arg in args:
            if arg.startswith('?'):
                rdf += f"""                    <swrl:argument1 rdf:resource="{self.namespace}{arg[1:]}"/>
"""
        
        rdf += "                </swrl:ClassAtom>\n"
        
        if not is_last:
            rdf += "                <rdf:rest>\n"
        else:
            rdf += "                <rdf:rest rdf:resource=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#nil\"/>\n"
        
        return rdf
    
    def _generate_owl_footer(self) -> str:
        return "</rdf:RDF>"


class JenaExporter:
    """Export to Jena Rules format"""
    
    def export(self, rules: List[SWRLRule], output_file: str):
        """Export to Jena rules format"""
        with open(output_file, 'w') as f:
            f.write("# Jena Rules for EU AI Act Compliance\n")
            f.write("# Generated from BPMN SWRL Rules\n\n")
            f.write("@prefix aiact: <http://example.org/aiact#> .\n\n")
            
            for rule in rules:
                # Comment
                f.write(f"# {rule.comment}\n")
                
                # Rule name
                f.write(f"[{rule.id}:\n")
                
                # Body
                body_clauses = []
                for atom in rule.body_atoms:
                    jena_atom = self._swrl_to_jena_atom(atom)
                    if jena_atom:
                        body_clauses.append(f"    {jena_atom}")
                
                f.write(",\n".join(body_clauses))
                f.write("\n  ->\n")
                
                # Head
                head_atom = self._swrl_to_jena_atom(rule.head_atom)
                f.write(f"    {head_atom}\n")
                f.write("]\n\n")
    
    def _swrl_to_jena_atom(self, atom: str) -> str:
        """Convert SWRL atom to Jena format"""
        # Handle negation
        negated = False
        if atom.startswith('not('):
            negated = True
            atom = atom[4:-1].strip()
        
        # Parse atom
        match = re.match(r'(\w+)\((.*?)\)', atom)
        if not match:
            return ""
        
        predicate = match.group(1)
        args_str = match.group(2)
        args = [arg.strip().strip("'\"") for arg in args_str.split(',')]
        
        # Convert to Jena format
        jena_args = []
        for arg in args:
            if arg.startswith('?'):
                jena_args.append(arg)  # Variables keep ?
            else:
                jena_args.append(f"'{arg}'")  # Literals get quotes
        
        jena_atom = f"({' '.join(['aiact:' + predicate] + jena_args)})"
        
        if negated:
            jena_atom = f"noValue{jena_atom}"
        
        return jena_atom


class PrologExporter:
    """Export to Prolog format"""
    
    def export(self, rules: List[SWRLRule], output_file: str):
        """Export to Prolog format"""
        with open(output_file, 'w') as f:
            f.write("% Prolog Rules for EU AI Act Compliance\n")
            f.write("% Generated from BPMN SWRL Rules\n\n")
            
            for rule in rules:
                # Comment
                f.write(f"% {rule.comment}\n")
                
                # Convert to Prolog syntax
                # Head :- Body.
                head = self._swrl_to_prolog_atom(rule.head_atom)
                
                body_atoms = [self._swrl_to_prolog_atom(atom) for atom in rule.body_atoms]
                body = ", ".join(body_atoms)
                
                f.write(f"{head} :- {body}.\n\n")
    
    def _swrl_to_prolog_atom(self, atom: str) -> str:
        """Convert SWRL atom to Prolog format"""
        # Handle negation
        if atom.startswith('not('):
            inner = atom[4:-1].strip()
            prolog_atom = self._swrl_to_prolog_atom(inner)
            return f"\\+ {prolog_atom}"
        
        # Parse atom
        match = re.match(r'(\w+)\((.*?)\)', atom)
        if not match:
            return atom
        
        predicate = match.group(1)
        args_str = match.group(2)
        args = [arg.strip() for arg in args_str.split(',')]
        
        # Convert SWRL variables (?x) to Prolog variables (X)
        prolog_args = []
        for arg in args:
            if arg.startswith('?'):
                # Capitalize first letter for Prolog variable
                var_name = arg[1:]
                var_name = var_name[0].upper() + var_name[1:]
                prolog_args.append(var_name)
            else:
                # Keep literals as-is
                prolog_args.append(arg)
        
        return f"{predicate}({', '.join(prolog_args)})"


class SWRLExecutableConverter:
    """Main converter class"""
    
    def __init__(self, input_file: str):
        self.input_file = input_file
        self.parser = SWRLParser()
        self.analyzer = VariableAnalyzer()
        self.enhancer = SWRLEnhancer()
    
    def convert(self, output_format: str, output_file: str):
        """Convert SWRL rules to executable format"""
        print(f"\n{'='*60}")
        print("SWRL TO EXECUTABLE FORMAT CONVERTER")
        print(f"{'='*60}")
        print(f"Input: {self.input_file}")
        print(f"Output Format: {output_format}")
        print(f"Output File: {output_file}")
        
        # Parse rules
        print("\n[1/4] Parsing SWRL rules...")
        rules = self.parser.parse_file(self.input_file)
        print(f"  Found {len(rules)} rules")
        
        # Analyze variables
        print("\n[2/4] Analyzing variable relationships...")
        analysis = self.analyzer.analyze(rules)
        print(f"  Disconnected rules: {len(analysis['disconnected_rules'])}")
        print(f"  Suggested relationships: {len(analysis['suggested_relationships'])}")
        
        if analysis['disconnected_rules']:
            print("\n  WARNING: Found disconnected variables in these rules:")
            for item in analysis['disconnected_rules']:
                print(f"    - {item['rule_id']}: {item['variables']}")
        
        # Enhance rules
        print("\n[3/4] Enhancing rules with relationship predicates...")
        enhanced_rules = self.enhancer.enhance_rules(rules)
        print(f"  Enhanced {len(enhanced_rules)} rules")
        
        # Export
        print(f"\n[4/4] Exporting to {output_format}...")
        if output_format == 'owl':
            exporter = OWLExporter()
            exporter.export(enhanced_rules, output_file)
        elif output_format == 'jena':
            exporter = JenaExporter()
            exporter.export(enhanced_rules, output_file)
        elif output_format == 'prolog':
            exporter = PrologExporter()
            exporter.export(enhanced_rules, output_file)
        else:
            raise ValueError(f"Unknown format: {output_format}")
        
        print(f"\n{'='*60}")
        print(f"✓ Successfully converted to {output_file}")
        print(f"{'='*60}\n")
        
        return enhanced_rules, analysis


# CLI
if __name__ == "__main__":
    import sys
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║  SWRL to Executable Format Converter                        ║
║  Adds relationship predicates and exports to executable     ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    if len(sys.argv) < 3:
        print("Usage: python swrl_executable.py <input.swrl> <output_file>")
        print("\nSupported output formats (auto-detected from extension):")
        print("  .owl    - OWL/RDF (for Protégé, Pellet, HermiT)")
        print("  .jena   - Jena Rules (for Apache Jena)")
        print("  .pl     - Prolog (for SWI-Prolog)")
        print("\nExample:")
        print("  python swrl_executable.py rules.swrl aiact.owl")
        print("  python swrl_executable.py rules.swrl aiact.jena")
        print("  python swrl_executable.py rules.swrl aiact.pl")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Detect format from extension
    ext = Path(output_file).suffix.lower()
    format_map = {
        '.owl': 'owl',
        '.rdf': 'owl',
        '.jena': 'jena',
        '.rules': 'jena',
        '.pl': 'prolog',
        '.prolog': 'prolog'
    }
    
    output_format = format_map.get(ext)
    if not output_format:
        print(f"Error: Unknown output format '{ext}'")
        print("Use .owl, .jena, or .pl extension")
        sys.exit(1)
    
    # Convert
    converter = SWRLExecutableConverter(input_file)
    converter.convert(output_format, output_file)
