import xml.etree.ElementTree as ET
from collections import defaultdict

from anyio import key, value

BPMN_NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}


class BPMNGraph:
    def __init__(self):
        self.nodes = {}          # node_id -> {"type": ..., "name": ...}
        self.outgoing = defaultdict(list)  # node_id -> [(flow_id, target_id)]
        self.flows = {}          # flow_id -> {"name": ..., "source": ..., "target": ...}
        self.start_events = set()
        self.end_events = set()

    def add_node(self, node_id, node_type, name=None):
        self.nodes[node_id] = {"type": node_type, "name": name}

    def add_flow(self, flow_id, source, target, name=None):
        self.flows[flow_id] = {
            "name": name,
            "source": source,
            "target": target,
        }
        self.outgoing[source].append((flow_id, target))


def parse_bpmn(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    graph = BPMNGraph()

    # Parse nodes
    for elem in root.findall(".//bpmn:*", BPMN_NS):
        tag = elem.tag.split("}")[-1]
        node_id = elem.get("id")
        if not node_id:
            continue

        name = elem.get("name")

        if tag == "startEvent":
            graph.add_node(node_id, "startEvent", name)
            graph.start_events.add(node_id)

        elif tag == "endEvent":
            graph.add_node(node_id, "endEvent", name)
            graph.end_events.add(node_id)

        elif tag.endswith("Gateway"):
            graph.add_node(node_id, tag, name)

        elif tag in {"task", "userTask", "serviceTask"}:
            graph.add_node(node_id, "task", name)

    # Parse flows
    for flow in root.findall(".//bpmn:sequenceFlow", BPMN_NS):
        flow_id = flow.get("id")
        src = flow.get("sourceRef")
        tgt = flow.get("targetRef")
        name = flow.get("name")
        graph.add_flow(flow_id, src, tgt, name)

    return graph


def enumerate_paths(graph):
    paths = []

    def dfs(current_node, visited, path):
        if current_node in visited:
            return  # loop detected

        visited.add(current_node)

        node_info = graph.nodes.get(current_node, {})
        path.append({
            "type": node_info.get("type"),
            "id": current_node,
            "name": node_info.get("name"),
        })

        if current_node in graph.end_events:
            paths.append(list(path))
        else:
            for flow_id, target in graph.outgoing.get(current_node, []):
                flow = graph.flows[flow_id]
                path.append({
                    "type": "sequenceFlow",
                    "id": flow_id,
                    "name": flow["name"],
                })
                dfs(target, visited, path)
                path.pop()

        path.pop()
        visited.remove(current_node)

    for start in graph.start_events:
        dfs(start, set(), [])


    simple_paths = []

    for i, path in enumerate(paths, 1):

        simple_path = []

        for step in path:
            if step["name"] is not None:

                if step["type"] == "exclusiveGateway":
                    simple_path.append({"condition": step['name']})
                if step["type"] == "parallelGateway":
                    continue
                if step["type"] == "task":
                    simple_path.append({"task": step['name']})
                if step["type"] == "sequenceFlow":
                    simple_path.append({"answer": step['name']})
        

        simple_paths.append(simple_path)

    return simple_paths





def print_swrl_rules_to_file(paths, filename="swrl_rules.txt"):

    swrl_rules = []
    human_readable_swrl_rules = []

    for i, path in enumerate(paths, 1):

        rule_name = "rule_" + str(i)

        conditions = []
        answers = []
        tasks = []


        for step in path:
            
            key = next(iter(step))
            
            value = step[key]

            if key =="condition":
                conditions.append(value[:-1])
            if key =="answer":
                answers.append(value)
            if key =="task":
                tasks.append(value)

        body_atoms = ""
        
        human_readable_swrl_rule = ""


        for condition, answer in zip(conditions, answers):

            condition_bool = "true" if answer == "Yes" else "false"

            body_atom = """<swrl:DatavaluedPropertyAtom>
                            \t\t\t\t<swrl:propertyPredicate rdf:resource="{condition_name_var}"/>
                            \t\t\t\t<swrl:argument1 rdf:resource="#?{actor_name_var}"/>
                            \t\t\t\t<swrl:argument2 rdf:datatype="&xsd;boolean">{condition_bool_var}</swrl:argument2>
                            \t\t</swrl:DatavaluedPropertyAtom>""".format(condition_name_var=condition.split(" ")[1], actor_name_var=condition.split(" ")[0], condition_bool_var=condition_bool)

            body_atoms += body_atom + "\n\t\t\t\t\t\t\t\t\t"

            if condition_bool == "true":
                human_readable_swrl_rule += condition.split(" ")[1] + "(?" + condition.split(" ")[0] + ") ^ "
            else:
                human_readable_swrl_rule += "not(" + condition.split(" ")[1] + "(?" + condition.split(" ")[0] + ")) ^ "  

        head_atoms = ""

        human_readable_swrl_rule = human_readable_swrl_rule [:-2] + " -> "

        for task in tasks:

            head_atom = """<swrl:DatavaluedPropertyAtom>
                            \t\t\t\t<swrl:propertyPredicate rdf:resource="#task"/>
                            \t\t\t\t<swrl:argument1 rdf:resource="#?{actor_name_var}"/>
                            \t\t\t\t<owlx:DataValue owlx:datatype="&xsd;string">{task_name_var}</owlx:DataValue>
                            \t\t</swrl:DatavaluedPropertyAtom>""".format(task_name_var=task.split(" ")[1], actor_name_var=task.split(" ")[0])
        
            head_atoms += head_atom + "\n\t\t\t\t\t\t\t\t\t"

            human_readable_swrl_rule += "task(?" + task.split(" ")[0] + ", " + '?' + task.split(" ")[1] + ") ^ "


        human_readable_swrl_rule = human_readable_swrl_rule[:-2]

        
        swrl_rule = """ \t\t\t\t\t\t<ruleml:imp>
                        \t<ruleml:_rlab ruleml:href="#{rule_name_var}"/>
                        \t\t<ruleml:_body> 
                        \t\t\t{body_atoms_var}
                        \t\t</ruleml:_body> 
                        \t\t<ruleml:_head> 
                        \t\t\t{head_atoms_var}
                        \t\t</ruleml:_head> 
                        </ruleml:imp>""".format(rule_name_var=rule_name, body_atoms_var=body_atoms[:-10], head_atoms_var=head_atoms[:-10])                                          

        swrl_rules.append(swrl_rule)

        human_readable_swrl_rules.append(human_readable_swrl_rule)

    with open(filename, "w", encoding="utf-8") as f:
        for i, (swrl_rule, human_readable_swrl_rule) in enumerate(zip(swrl_rules, human_readable_swrl_rules)):
            f.write("#PATH " + str(i+1) + " " + "\n" + "#Human-readable SWRL: " + human_readable_swrl_rule + "\n\n" + swrl_rule + "\n\n\n")






if __name__ == "__main__":

    import sys

    bpmn_file = sys.argv[1]


    graph = parse_bpmn(bpmn_file)
    paths = enumerate_paths(graph)


    print_swrl_rules_to_file(paths, bpmn_file.replace(".bpmn", "_swrl_rules.txt"))



