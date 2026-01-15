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

    return paths


def pretty_print_paths_OLD(paths):
    for i, path in enumerate(paths, 1):
        print(f"\nPath {i}:")
        for step in path:
            if step["type"] == "sequenceFlow" and step['name'] is not None:
                #print(f"  --[{step['id']} | {step['name']}]-->")
                print(step['name'])
            else:
                if step['type'] == "exclusiveGateway":
                    print("CONDITION:", step['name'])
                if step['type'] == "parallelGateway":
                    continue
                if step['type'] == "task":
                    print("OBLIGATION:", step['name'])
                #
                
                #print(f"  ({step['type']}) {step['id']} : {step['name']}")
                print(step['name'])






def pretty_print_paths(paths):
    for i, path in enumerate(paths, 1):
        print("PATH: ", i)
        for step in path:
            if step["name"] is not None:
                if step['type'] == "exclusiveGateway":
                    print("CONDITION:", step['name'])
                if step['type'] == "parallelGateway":
                    continue
                if step['type'] == "task":
                    print("OBLIGATION:", step['name'])
                if step['type'] == "sequenceFlow":
                    print("ANSWER: ", step['name'])
        print("\n")






def create_human_readable_swrl(paths):

    strings = []

    for i, path in enumerate(paths, 1):

        conditions = []
        answers = []
        tasks = []


        for step in path:
            
            key = next(iter(step))
            
            value = step[key]
            print(key, value)

            if key =="condition":
                conditions.append(value)
            if key =="answer":
                answers.append(value)
            if key =="task":
                tasks.append(value)


        print(answers)

        string = ""

        for condition, answer in zip(conditions, answers):

            print(answer)
            if answer == "Yes":
                bowl = "true"
            else:
                bowl = "false"


            string += condition.split(" ")[1] + "(?" + condition.split(" ")[0] +  ", " + bowl + ") ^ "


        string = string [:-2] + " -> "

        for task in tasks:
            string += "task(?" + task.split(" ")[1] + ", " + '"' + task.split(" ")[0] + '"' + ") ^ "


        string = string[:-2]

        strings.append(string)

    return strings






def simple_paths_save(paths):

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

if __name__ == "__main__":
    bpmn_file = "interaction.bpmn"

    graph = parse_bpmn(bpmn_file)
    paths = enumerate_paths(graph)
    print(paths)
    pretty_print_paths(paths)
    print(simple_paths_save(paths))

    human_strings = create_human_readable_swrl(simple_paths_save(paths))
    [print(human_string) for human_string in human_strings]







def create_swrl(paths):

    template_str = """ <ruleml:imp>
                            <ruleml:_rlab ruleml:href="#example1"/>
                            <ruleml:_body> 
                                <swrl:DatavaluedPropertyAtom>
                                    <swrl:propertyPredicate rdf:resource="#task"/>
                                    <swrl:argument1 rdf:resource="#?x"/>
                                    <owlx:DataValue owlx:datatype="&xsd;string">Marking Obligation</owlx:DataValue>
                                </swrl:DatavaluedPropertyAtom>
                                <swrl:DatavaluedPropertyAtom>
                                    <swrl:propertyPredicate rdf:resource="#justEditing"/>
                                    <swrl:argument1 rdf:resource="#?x"/>
                                    <swrl:argument2 rdf:datatype="&xsd;boolean">true</swrl:argument2>
                                </swrl:DatavaluedPropertyAtom>
                            </ruleml:_body> 
                            <ruleml:_head> 
                                <swrl:DatavaluedPropertyAtom>
                                    <swrl:propertyPredicate rdf:resource="#task"/>
                                    <swrl:argument1 rdf:resource="#?x"/>
                                    <owlx:DataValue owlx:datatype="&xsd;string">Volutary codes of conduct</owlx:DataValue>
                                </swrl:DatavaluedPropertyAtom>
                            </ruleml:_head> 
                            </ruleml:imp>"""
    

    #for i, path in enumerate(paths, 1):

    #    rule_name = "rule_" + str(i)

