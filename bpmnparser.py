import xml.etree.ElementTree as ET
import os
from typing import Dict
import re
from collections import defaultdict


processes: [ET.Element] = []

process_names: Dict[str, str] = {}

messages_names = defaultdict(list)

messages_sources = {}
messages_targets = {}

objects_process = defaultdict(list)

communicating_processes = defaultdict(list)


def produce_solidity_from_bpmn(bpmn_path: str, out_dir: str):
    parse(bpmn_path)
    try:
        os.mkdir(out_dir)
    except FileExistsError:
        print
        "Warning: <./generated> folder already exists"

    for process in processes:
        out_process_sc = open(out_dir + process_names[name_or_id(process)] + ".sol", "w+")
        out_process_sc.write(bpmnprocess_to_soliditysc(process))
        out_process_sc.close()

    owned = "contract Owned{\n"
    owned += "\taddress owner;\n\n"
    owned += "\tmodifier onlyOwner(){\n"
    owned += "\t\trequire(msg.sender == owner);\n"
    owned += "\t\t_;\n"
    owned += "\t}\n"
    owned += "}"

    out_process_owned = open(out_dir + "Owned.sol", "w+")
    out_process_owned.write(owned)
    out_process_owned.close()


def parse(xml_path: str):
    root = ET.parse(xml_path).getroot()
    parse_out_collaboration(root)
    parse_out_processes(root)
    compute_communicating_processes()


def parse_out_collaboration(node: ET.Element) -> [str]:
    child: ET.Element
    for child in node:
        if "collaboration" in child.tag:
            grandchild: ET.Element
            for grandchild in child:
                if "participant" in grandchild.tag:
                    process_names[grandchild.attrib["processRef"]] = clean_string(grandchild.attrib["name"])
                elif "messageFlow" in grandchild.tag:
                    source_ref: str = grandchild.attrib["sourceRef"]
                    target_ref: str = grandchild.attrib["targetRef"]
                    if "name" in grandchild.attrib:
                        messages_names[source_ref] = grandchild.attrib["name"]
                    else:
                        messages_names[source_ref] = source_ref + "_to_" + target_ref
                    messages_targets[source_ref] = target_ref
                    messages_sources[target_ref] = source_ref


def parse_out_processes(node: ET.Element) -> [str]:
    for child in node:
        if "process" in child.tag:
            label_children(child)
            processes.append(child)


def label_children(node: ET.Element):
    for child in node:
        objects_process[child.attrib["id"]] = node.attrib["id"]


def compute_communicating_processes():
    for source in messages_targets.keys():
        source_process = objects_process[source]
        target_process = objects_process[messages_targets[source]]

        communicating_processes[source_process].append(target_process)
        communicating_processes[target_process].append(source_process)


# events must be triggered by external call
# constructor parametrised by connected processes
# activities must automatically be executed, we only wait for event


def bpmnprocess_to_soliditysc(node: ET.Element) -> str:
    current_sequence_flows = [child for child in node if "startEvent" in child.tag]

    smart_contract = 'import "./Owned.sol";\n\n'
    smart_contract += 'contract ' + clean_string(process_names[node.attrib["id"]]) + ' is Owned{\n\n'

    flow_objects = {name_or_id(child) for child in node if "Flow" not in child.attrib["id"] and "Association" not in child.attrib["id"] and "LaneSet" not in child.attrib["id"]}

    smart_contract += "\tenum FlowObjects {" + \
                      ",".join(flow_objects) + \
                      "}\n\n"
    smart_contract += "\tFlowObjects[] current;\n\n"

    related_processes = [clean_string(process_names[id]) for id in communicating_processes[node.attrib["id"]]]

    for communicating_process in ["address " + process_name for process_name in related_processes]:
        smart_contract += "\t" + communicating_process + ";\n\n"

    smart_contract += "\tconstructor("

    smart_contract += ", ".join(["address _" + process_name for process_name in related_processes])

    smart_contract += ") public{\n"
    smart_contract += "\t\towner = msg.sender;\n"
    params = ["\t\t" + related_process + " = _" + related_process + ";\n" for related_process in related_processes]
    smart_contract += "".join(params)
    smart_contract += "\n"
    smart_contract += "\t\tcurrent[0] = FlowObjects." + name_or_id(current_sequence_flows[0]) + ";\n"
    smart_contract += "\t}\n\n"

    flow_code: Dict[str, str] = {}

    already_done: [str] = []

    while len(current_sequence_flows) != 0:
        next_sequence_flows = []
        for child in current_sequence_flows:
            identifier = name_or_id(child)

            if identifier not in flow_code.keys():
                flow_code[identifier] = ""

                # check if is the target of a message flow
                # if yes then set a require to the msg sender being the source of the message flow

                if "id" in child.attrib and child.attrib["id"] in messages_sources.keys():
                    source_process_name = clean_string(process_names[objects_process[messages_sources[child.attrib["id"]]]])
                    flow_code[identifier] += "\tfunction trigger_" + identifier + "() public {\n"
                    flow_code[identifier] += "\t\trequire(msg.sender == " + source_process_name + ");\n\n"
                else:
                    flow_code[identifier] += "\tfunction trigger_" + identifier + "() onlyOwner public {\n"

                if "id" in child.attrib and child.attrib["id"] in messages_targets.keys():
                    target_process_name = clean_string(process_names[objects_process[messages_targets[child.attrib["id"]]]])
                    flow_code[identifier] += "\t\t" + target_process_name + ".call(abi.encodeWithSignature(\"trigger_" + clean_string(messages_targets[child.attrib["id"]]) + "()\"));\n\n"

                flow_code[identifier] += "\t\tuint len = current.length;\n"
                flow_code[identifier] += "\t\tfor(uint i = 0; i < len; i++){\n"

            outgoing_flows = [obj for grandchild in child for obj in node if
                              "outgoing" in grandchild.tag and grandchild.text == obj.attrib["id"]]

            function_call = ""

            if "parallel" in child.tag:
                flow_code[identifier] += "\t\t\tif(current[i] == FlowObjects." + name_or_id(child) + "){\n"

                flow_code[identifier] += function_call

                first: bool = True;
                for outgoing_flow in outgoing_flows:
                    outgoing_object_ref = outgoing_flow.attrib["targetRef"]
                    outgoing_object = [obj for obj in node if obj.attrib["id"] == outgoing_object_ref][0]
                    if first:
                        flow_code[identifier] += "\t\t\t\t" + "current[i] = FlowObjects." + name_or_id(
                            outgoing_object) + ";\n"
                        first = False;
                    else:
                        flow_code[identifier] += "\t\t\t\t" + "current.push(FlowObjects." + name_or_id(
                            outgoing_object) + ");\n"
                    if "endEvent" not in outgoing_object.tag and outgoing_object not in already_done:
                        next_sequence_flows.append(outgoing_object)
                flow_code[identifier] += "\t\t\t}\n"
            else:
                for outgoing_flow in outgoing_flows:
                    outgoing_object_ref = outgoing_flow.attrib["targetRef"]
                    outgoing_object = [obj for obj in node if obj.attrib["id"] == outgoing_object_ref][0]
                    flow_code[identifier] += "\t\t\tif(current[i] == FlowObjects." + name_or_id(child) + "){\n"
                    flow_code[identifier] += function_call
                    flow_code[identifier] += "\t\t\t\tcurrent[i] = FlowObjects." + name_or_id(outgoing_object) + ";\n"
                    flow_code[identifier] += "\t\t\t}\n"

                    if "endEvent" not in outgoing_object.tag and outgoing_object not in already_done:
                        next_sequence_flows.append(outgoing_object)

        already_done.extend(current_sequence_flows)
        current_sequence_flows = next_sequence_flows

    for key in flow_code:
        flow_code[key] += "\t\t}\n"
        flow_code[key] += "\t}\n\n"
        smart_contract += flow_code[key]

    smart_contract += "}"
    return smart_contract


def name_or_id(node: ET.Element) -> str:
    if "name" in node.attrib.keys():
        return clean_string(node.attrib["name"])
    elif not "id" in node.attrib.keys():
        return clean_string(node.text)
    else:
        return node.attrib["id"]


def clean_string(text: str) -> str:
    without_whitespace: str = text.strip(" ").replace(" ", "_")
    without_text_in_brackets: str = without_whitespace
    for bracket_text in re.findall(re.compile(".*?\((.*?)\)"), without_whitespace):
        without_text_in_brackets = without_text_in_brackets.replace(bracket_text, "")
    without_punctuation: str = without_text_in_brackets
    for punct in '''!()-[]{};:'"\,<>./?@#$%^&*~+''':
        without_punctuation = without_punctuation.replace(punct, "")
    return without_punctuation.strip("_")
