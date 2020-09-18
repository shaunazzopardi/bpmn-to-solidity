import xml.etree.ElementTree as ET
import os
from typing import Dict
import re
from collections import defaultdict

########################################################################################################################
########################################################################################################################
########################################################################################################################

# Variables

# List of processes fully on chain as XML elements
brokers: [ET.Element] = []

# List of processes as XML elements
only_event_processes: [ET.Element] = []

# Process ID <-> Participant name
# Potential problem: Implementation uses name_or_id not process.attrib["id"]
process_names: Dict[str, str] = {}

# Message ID <-> Message/Arrow Label
message_name: Dict[str, str] = {}

# Message ID <-> Message/Arrow Action (OnChain event, or Swap)
message_action: Dict[str, str] = {}

# List of flow objects that are the source of messages flows
message_target_to_source = {}

# List of flow objects that are the target of messages flows
message_source_to_target = {}

message_flow_to_source = {}

message_flow_to_target = {}

message_source_to_flow = {}

message_target_to_flow = {}

# FlowObject ID <-> Process ID
object_s_process: Dict[str, str] = {}

# Process ID <-> Process ID
communicating_processes = defaultdict(list)

# TODO turn this into function annotations
# Flow Object ID <-> String
text_annotations = defaultdict(list)

# Process ID <-> Participant ID
processes_participant = defaultdict(list)

# Flow Object ID <-> Text Annotation ID
object_tag = defaultdict(list)

# Flow Object ID <-> Name String
object_name = {}

# Process <-> Blockchain
process_blockchain: Dict[str, str] = {}

# Flow Object ID <-> Token
object_tokens: Dict[str, str] = {}

# Process <-> Token
process_tokens = defaultdict(set)

# Info on tokes
token_info: Dict[str, str]


########################################################################################################################
########################################################################################################################
########################################################################################################################

# Functions

# Input
#       bpmn_path - Path to *.bpmn file
#       out_dir   - Path to output directory (does not need to exist)
#
# Output
#       Nada
#
# Effects
#       Saves Solidity files at bpmn_path to out_dir.
#
# Description
#       Generates Solidity files corresponding to the input BPMN file.


def produce_solidity_from_bpmn(bpmn_path: str, out_dir: str, mult_chain_mode: bool):
    parse(bpmn_path)
    try:
        os.mkdir(out_dir)
    except FileExistsError:
        print
        "Warning: <./generated> folder already exists"

    for process in brokers + only_event_processes:
        try:
            os.mkdir(out_dir + process_blockchain[name_or_id(process)])
        except FileExistsError:
            print
            "Warning: <./generated/" + process_blockchain[name_or_id(process)] + "> folder already exists"

        out_process_sc = open(
            out_dir + process_blockchain[name_or_id(process)] + "/" + process_names[name_or_id(process)] + ".sol", "w+")
        out_process_sc.write(bpmn_smart_contract(process, process in brokers))
        out_process_sc.close()

    for chain in process_blockchain.values():
        brokers_here = [broker for broker in brokers if process_blockchain[broker.attrib["id"]] == chain]
        listeners_here = [listener for listener in only_event_processes if
                          process_blockchain[listener.attrib["id"]] == chain]

        try:
            os.mkdir(out_dir + "/" + chain)
        except FileExistsError:
            print
            "Warning: <./generated/" + chain + "> folder already exists"

        out_process_sc = open(
            out_dir + "/" + chain + "/monolithic.sol", "w+")
        out_process_sc.write(bpmn_smart_contract_monolithic("Monolithic", brokers_here, listeners_here))
        out_process_sc.close()

    # for process in only_event_processes:
    #     try:
    #         os.mkdir(out_dir + process_blockchain[name_or_id(process)])
    #     except FileExistsError:
    #         print
    #         "Warning: <./generated/" + process_blockchain[name_or_id(process)] + "> folder already exists"
    #
    #     out_process_sc = open(
    #         out_dir + process_blockchain[name_or_id(process)] + "/" + process_names[name_or_id(process)] + ".sol", "w+")
    #     out_process_sc.write(only_events_process_to_solidity(process))
    #     out_process_sc.close()

    try:
        os.mkdir(out_dir + "notary")
    except FileExistsError:
        print
        "Warning: <./notary> folder already exists"

    out_process_sc = open(
        out_dir + "notary/notary.js", "w+")
    out_process_sc.write(generate_notary())
    out_process_sc.close()

    try:
        os.mkdir(out_dir + "test")
    except FileExistsError:
        print
        "Warning: <./test> folder already exists"

    out_process_sc = open(
        out_dir + "test/test.js", "w+")
    out_process_sc.write(generate_testing_code(False))
    out_process_sc.close()

    out_process_sc = open(
        out_dir + "test/test-monolithic.js", "w+")
    out_process_sc.write(generate_testing_code(True))
    out_process_sc.close()


# Input
#       bpmn_path - Path to *.bpmn file
#
# Output
#       Nada
#
# Effects
#       Populates all global state variables according to file at bpmn_path
#
# Description
#       Parses input BPMN file, gathering all information required to generate corresponding Solidity files.


def parse(bpmn_path: str):
    root = ET.parse(bpmn_path).getroot()
    parse_out_collaboration(root)
    parse_out_processes(root)
    compute_communicating_processes()


# Input
#       node - Root of a *.bpmn file
#
# Output
#       Nada
#
# Effects
#       Populates process_names, processes_participant, message_name, message_target_to_source,
#       message_source_to_target, text_annotations, and object_tag.
#
# Description
#       Parses bpmn:collaboration node in BPMN file, that records communication between participants.


def parse_out_collaboration(node: ET.Element):
    child: ET.Element
    for child in node:
        if "collaboration" in child.tag:
            grandchild: ET.Element
            for grandchild in child:
                if "participant" in grandchild.tag:
                    name = grandchild.attrib["name"]
                    actual_name = re.sub(r" *@Chain.*", "", name)
                    chain_ref = name.replace(actual_name, "").replace("@Chain", "").replace("(", "").replace(")", "") \
                        .strip(" ")

                    process_names[grandchild.attrib["processRef"]] = clean_string(actual_name)
                    processes_participant[grandchild.attrib["processRef"]] = grandchild.attrib["id"]
                    if chain_ref != "":
                        process_blockchain[grandchild.attrib["processRef"]] = chain_ref
                elif "messageFlow" in grandchild.tag:
                    id: str = grandchild.attrib["id"]
                    source_ref: str = grandchild.attrib["sourceRef"]
                    target_ref: str = grandchild.attrib["targetRef"]

                    message_flow_to_source[id] = source_ref
                    message_flow_to_target[id] = target_ref

                    message_source_to_flow[source_ref] = id
                    message_target_to_flow[target_ref] = id

                    if "name" in grandchild.attrib:
                        name = grandchild.attrib["name"].strip(" ")
                        if "@" in name:
                            actual_name = re.sub(r"\[[^\[\]]*\]", "", name).strip(" ").strip("\n")
                            message_name[id] = actual_name

                            action = name.replace(actual_name, "").replace("[", "").replace("]", "") \
                                .strip(" ").strip("\n")
                            message_action[id] = action

                            if action.startswith('@Swap'):
                                sent = get_sent_token(action)
                                if sent.lower() != "eth":
                                    object_tokens[source_ref] = sent

                                received = get_received_token(action)
                                if received.lower() != "eth":
                                    object_tokens[target_ref] = received

                            elif action.startswith('@Transfer'):
                                sent = get_sent_token(action)
                                if sent.lower() != "eth":
                                    object_tokens[source_ref] = sent

                        else:
                            message_name[id] = name
                    else:
                        message_name[id] = source_ref + "_to_" + target_ref
                    message_source_to_target[source_ref] = target_ref
                    message_target_to_source[target_ref] = source_ref
                elif "textAnnotation" in grandchild.tag:
                    for greatgrandchild in grandchild:
                        if "text" in greatgrandchild.tag:
                            text_annotations[grandchild.attrib["id"]] = greatgrandchild.text
                elif "association" in grandchild.tag:
                    object_tag[grandchild.attrib["sourceRef"]] = grandchild.attrib["targetRef"]


def get_sent_token(action: str):
    sent1 = re.sub(r"^(.|\n)+(?=Send:)", "", action)
    return re.sub(r"\n.*", "", sent1).replace("Send:", "").strip(" ")


def get_received_token(action: str):
    received1 = re.sub(r"^(.|\n)+(?=Receive:)", "", action)
    return re.sub(r"\n.*", "", received1).replace("Receive:", "").strip(" ")


# Input
#       node - Root of a *.bpmn file
#
# Output
#       Nada
#
# Effects
#       Populates object_s_process, brokers, only_event_processes, and object_tag.
#
# Description
#       Parses bpmn:process node in BPMN file.


def parse_out_processes(node: ET.Element):
    for child in node:
        object_name[child.attrib["id"]] = clean_string(name_or_id(child))
        if "process" in child.tag:
            label_children_s_parents(child)
            process_participant = processes_participant[child.attrib["id"]]
            if process_participant in object_tag.keys():
                if "broker" in text_annotations[object_tag[process_participant]].lower():
                    brokers.append(child)
            else:
                only_event_processes.append(child)
            for grandchild in child:
                if "association" in grandchild.tag:
                    object_tag[grandchild.attrib["sourceRef"]] = grandchild.attrib["targetRef"]


# Input
#       node - Root of bpmn:process node
#
# Output
#       Nada
#
# Effects
#       Populates object_s_process.
#
# Description
#       Labels flow objects with the process in which they occur in.


def label_children_s_parents(process_node: ET.Element):
    for child in process_node:
        process_id = process_node.attrib["id"]
        child_id = child.attrib["id"]
        object_s_process[child_id] = process_id
        object_name[child_id] = clean_string(name_or_id(child))
        if child_id in object_tokens.keys():
            process_tokens[process_id].add(object_tokens[child_id])


# Input
#       Nada
#
# Output
#       Nada
#
# Effects
#       Populates source_process, target_process, communicating_processes.
#
# Description
#       Identifies processes that communicate with each other.


def compute_communicating_processes():
    for source in message_source_to_target.keys():
        source_process = object_s_process[source]
        target_process = object_s_process[message_source_to_target[source]]

        communicating_processes[source_process].append(target_process)
        communicating_processes[target_process].append(source_process)


# Input
#       node - Root of bpmn:process node
#
# Output
#       Solidity smart contract
#
# Effects
#       Nada
#
# Description
#       Generates Solidity smart contract corresponding to the event logic of the input BPMN process.


def bpmn_functions_event_recorder(node: ET.Element, monolithic: bool) -> str:
    functions = ""
    for child in node:
        identifier = object_name[child.attrib["id"]]

        event_name = clean_string(identifier)
        function_name = "trigger_" + event_name

        preamb = "\n\n\tevent " + event_name + "(address indexed _from, address indexed _to);\n\n"

        if "id" in child.attrib and child.attrib["id"] in message_target_to_source.keys():
            functions += preamb
            function_code = "\tfunction " + function_name + "(address _to, $params) $modifiers public {\n"

            function_code = transfer_and_swap_logic(node, child, function_code, monolithic)

            function_code = function_code.replace(", $params", "")
            function_code = function_code.replace("$params", "")

            function_code += "\t\temit " + event_name + "(msg.sender, _to);\n"

            functions += function_code
            functions += "\t}\n"
        elif "id" in child.attrib and child.attrib["id"] in message_source_to_target.keys():
            functions += preamb

            collab_event = clean_string(message_name[message_source_to_flow[child.attrib["id"]]])

            function_code = "\tevent " + collab_event + "(address _from, address _to);\n\n"
            function_code += "\tfunction trigger_" + identifier + "($params) only(" + process_names[
                node.attrib["id"]] + ") public {\n"
            function_code = transfer_and_swap_logic(node, child, function_code, monolithic)

            function_code = function_code.replace("$params", "")
            function_code = function_code.replace("$modifiers", "")
            function_code += "\t\temit " + collab_event + "(msg.sender, _to);\n"

            function_code += "\t\temit " + event_name + "(msg.sender);\n"

            functions += function_code
            functions += "\t}\n"
        elif "Event" in child.tag:
            functions += preamb
            functions += "\tfunction " + function_name + "(address _to) only(" + process_names[
                node.attrib["id"]] + ") public {\n"
            functions += "\t\temit " + event_name + "(msg.sender, _to);\n"
            functions += "\t}\n"


    return functions


# Input
#       node - Root of bpmn:process node
#
# Output
#       Solidity smart contract
#
# Effects
#       Nada
#
# Description
#       Generates Solidity smart contract corresponding to the flow and event logic of the input BPMN process.

def bpmn_smart_contract(node: ET.Element, broker: bool) -> str:
    smart_contract = bpmn_preamble()

    smart_contract += 'contract ' + clean_string(process_names[node.attrib["id"]]) + ' is Only{\n\n'
    smart_contract += bpmn_local_state(node, broker)
    smart_contract += bpmn_constructor(node, broker)

    if broker:
        smart_contract += bpmn_functions_broker(node, False)
    else:
        smart_contract += bpmn_functions_event_recorder(node, False)
    smart_contract += "\n}"

    return smart_contract.replace("\n\n\n", "\n\n")


def bpmn_smart_contract_monolithic(name: str, brokers: [ET.Element], listeners: [ET.Element]) -> [str]:
    smart_contract = bpmn_preamble()
    smart_contract += 'contract ' + clean_string(name) + ' is Only, HashedTimelock, HashedTimelockERC20{\n\n'

    smart_contract += bpmn_local_state_monolithic(brokers, listeners)
    smart_contract += bpmn_constructor_monolithic(brokers, listeners)

    for broker in brokers:
        smart_contract += bpmn_functions_broker(broker, True)

    for event_recorder in listeners:
        smart_contract += bpmn_functions_event_recorder(event_recorder, True)

    smart_contract += "\n}"

    return smart_contract.replace("\n\n\n", "\n\n")


def bpmn_preamble() -> str:
    preamble = 'import "./Only.sol";\n'
    preamble += 'import "./IERC20.sol";\n'
    preamble += 'import "./HashedTimelock.sol";\n'
    preamble += 'import "./HashedTimelockERC20.sol";\n\n'

    return preamble


def get_related_processes(node: ET.Element) -> [str]:
    return {clean_string(process_names[id]) for id in communicating_processes[node.attrib["id"]]}


def bpmn_local_state(node: ET.Element, broker: bool) -> str:
    local_state = ""

    if broker:
        flow_objects = {name_or_id(child) for child in node if
                        "Flow" not in child.attrib["id"] and "Association" not in child.attrib[
                            "id"] and "LaneSet" not in
                        child.attrib["id"]}

        local_state += "\tenum FlowObjects" + process_names[node.attrib["id"]] + " {" + \
                       ",".join(flow_objects) + \
                       "}\n\n"
        local_state += "\tFlowObjects" + process_names[node.attrib["id"]] + "[] current" + process_names[
            node.attrib["id"]] + ";\n\n"

    related_processes = get_related_processes(node)

    for communicating_process in {"address " + process_name for process_name in related_processes}:
        local_state += "\t" + communicating_process + ";\n\n"

    for token in ["ERC20 " + token_name + "_token" for token_name in process_tokens[node.attrib["id"]]]:
        local_state += "\t" + token + ";\n"

    local_state += "\taddress notary;\n\n"
    local_state += "\taddress " + process_names[node.attrib["id"]] + ";\n\n"

    return local_state


def bpmn_local_state_monolithic(brokers: [ET.Element], listeners: [ET.Element]) -> str:
    local_state = ""

    for broker in brokers:
        flow_objects = {name_or_id(child) for child in broker if
                        "Flow" not in child.attrib["id"] and "Association" not in child.attrib[
                            "id"] and "LaneSet" not in
                        child.attrib["id"]}

        name = clean_string(name_or_id(broker))

        local_state += "\tenum FlowObjects" + name + " {" + \
                       ",".join(flow_objects) + \
                       "}\n\n"
        local_state += "\tFlowObjects" + name + "[] current" + name + ";\n\n"

    related_processes = {process_names[node.attrib["id"]] for node in brokers + listeners}

    for communicating_process in {"address " + process_name for process_name in related_processes}:
        local_state += "\t" + communicating_process + ";\n\n"

    for token in ["ERC20 " + token_name + "_token" for token_name in object_tokens.values()]:
        local_state += "\t" + token + ";\n"

    local_state += "\taddress notary;\n\n"

    return local_state


def bpmn_constructor(node: ET.Element, broker: bool) -> str:
    current_sequence_flows = [child for child in node if "startEvent" in child.tag]
    related_processes = get_related_processes(node)

    name = process_names[node.attrib["id"]]

    constructor = "\tconstructor("

    params = {"address _" + process_name for process_name in related_processes}
    params.update({"address _" + token_name + "_token" for token_name in process_tokens[node.attrib["id"]]})
    params.update({"address _notary"})
    params.update({"address _" + name})
    constructor += ", ".join(params)

    constructor += ") public{\n"
    constructor += "\t\tname = msg.sender;\n"
    setters = {"\t\t" + related_process + " = _" + related_process + ";\n" for related_process in related_processes}
    setters.update({"\t\t" + token_name + "_token = ERC20(_" + token_name + "_token);\n" for token_name in
                    process_tokens[node.attrib["id"]]})
    setters.update({"\t\tnotary = _notary;\n"})
    setters.update({"\t\t" + name + " = _" + name + ";\n"})
    constructor += "".join(setters)
    if broker:
        constructor += "\n\t\tcurrent" + process_names[node.attrib["id"]] + "[0] = FlowObjects" + process_names[
            node.attrib["id"]] + "." + name_or_id(current_sequence_flows[0]) + ";\n"
    constructor += "\t}\n\n"

    return constructor


def bpmn_constructor_monolithic(brokers: [ET.Element], listeners: [ET.Element]) -> str:
    related_processes = {process_names[node.attrib["id"]] for node in brokers + listeners}

    constructor = "\tconstructor("

    params = {"address _" + process_name for process_name in related_processes}
    params.update({"address _" + token_name + "_token" for token_name in object_tokens.values()})
    params.update({"address _notary"})
    constructor += ", ".join(params)

    constructor += ") public{\n"
    setters = {"\t\t" + related_process + " = _" + related_process + ";\n" for related_process in related_processes}
    setters.update(
        {"\t\t" + token_name + "_token = ERC20(_" + token_name + "_token);\n" for token_name in object_tokens.values()})
    setters.update({"\t\tnotary = _notary;\n"})
    constructor += "".join(setters)
    for broker in brokers:
        current_sequence_flows = [child for child in broker if "startEvent" in child.tag]
        constructor += "\n\t\tcurrent" + process_names[broker.attrib["id"]] + "[0] = FlowObjects" + process_names[
            broker.attrib["id"]] + "." + name_or_id(current_sequence_flows[0]) + ";\n"
    constructor += "\t}\n\n"

    return constructor


def bpmn_functions_broker(node: ET.Element, monolithic: bool) -> str:
    current_sequence_flows = [child for child in node if "startEvent" in child.tag]

    flow_code: Dict[str, str] = {}

    already_done: [str] = []

    while len(current_sequence_flows) != 0:
        next_sequence_flows = []
        for child in current_sequence_flows:
            identifier = name_or_id(child)

            if identifier not in flow_code.keys():
                flow_code[
                    identifier] = "\t$events\n\n\tfunction trigger_" + identifier + "($params) $modifiers public {\n"

                flow_code[identifier] = transfer_and_swap_logic(node, child, flow_code[identifier], monolithic)

                flow_code[identifier] = flow_code[identifier].replace(", $params", "")
                flow_code[identifier] = flow_code[identifier].replace("$params", "")
                flow_code[identifier] = flow_code[identifier].replace("$modifiers", "only(" + process_names[
                    object_s_process[child.attrib["id"]]] + ")")

                flow_code[identifier] += "\t\tuint len = current.length;\n"
                flow_code[identifier] += "\t\tfor(uint i = 0; i < len; i++){\n"

            outgoing_flows = [obj for grandchild in child for obj in node if
                              "outgoing" in grandchild.tag and grandchild.text == obj.attrib["id"]]

            function_call = ""

            if "id" in child.attrib.keys():
                child_id = child.attrib["id"]
                if child_id in object_tag.keys():
                    function_call = "\t\t\t\t" + text_annotations[object_tag[child_id]] + ";\n"

            if "parallel" in child.tag:
                flow_code[identifier] += "\t\t\tif(current" + process_names[node.attrib["id"]] + "[i] == FlowObjects" + \
                                         process_names[node.attrib["id"]] + "." + name_or_id(child) + "){\n"

                flow_code[identifier] += function_call

                first: bool = True
                for outgoing_flow in outgoing_flows:
                    outgoing_object_ref = outgoing_flow.attrib["targetRef"]
                    outgoing_object = [obj for obj in node if obj.attrib["id"] == outgoing_object_ref][0]
                    if first:
                        flow_code[identifier] += "\t\t\t\t" + "current" + process_names[
                            node.attrib["id"]] + "[i] = FlowObjects" + process_names[
                                                     node.attrib["id"]] + "." + name_or_id(
                            outgoing_object) + ";\n"
                        first = False
                    else:
                        flow_code[identifier] += "\t\t\t\t" + "current" + process_names[
                            node.attrib["id"]] + ".push(FlowObjects" + process_names[
                                                     node.attrib["id"]] + "." + name_or_id(
                            outgoing_object) + ");\n"
                    if "endEvent" not in outgoing_object.tag and outgoing_object not in already_done:
                        next_sequence_flows.append(outgoing_object)
                flow_code[identifier] += "\t\t\t}\n"
            else:
                for outgoing_flow in outgoing_flows:
                    outgoing_object_ref = outgoing_flow.attrib["targetRef"]
                    outgoing_object = [obj for obj in node if obj.attrib["id"] == outgoing_object_ref][0]
                    flow_code[identifier] += "\t\t\tif(current" + process_names[
                        node.attrib["id"]] + "[i] == FlowObjects" + process_names[node.attrib["id"]] + "." + name_or_id(
                        child) + "){\n"
                    flow_code[identifier] += function_call
                    flow_code[identifier] += "\t\t\t\tcurrent" + process_names[
                        node.attrib["id"]] + "[i] = FlowObjects" + process_names[node.attrib["id"]] + "." + name_or_id(
                        outgoing_object) + ";\n"
                    flow_code[identifier] += "\t\t\t}\n"

                    if "endEvent" not in outgoing_object.tag and outgoing_object not in already_done:
                        next_sequence_flows.append(outgoing_object)

            if "id" in child.attrib.keys() and child.attrib["id"] in message_source_to_target.keys():
                collab_event = clean_string(message_name[message_source_to_flow[child.attrib["id"]]])
                event_def = "event " + collab_event + "(address _from, address _to);"
                flow_code[identifier] = flow_code[identifier].replace("$events", event_def)
                flow_code[identifier] += "\t\t\temit " + collab_event + "(msg.sender, _to);\n"
            else:
                flow_code[identifier] = flow_code[identifier].replace("$events", "")

        already_done.extend(current_sequence_flows)
        current_sequence_flows = next_sequence_flows

    function_body = ""

    for key in flow_code:
        flow_code[key] += "\t\t}\n\n"
        flow_code[key] += "\t}"
        function_body += flow_code[key]

    function_body += "\n\n\tfunction current_" + name_or_id(node) + \
                      "() view public returns(FlowObjects" + name_or_id(node) + "){\n"
    function_body += "\t\treturn current" + name_or_id(node) + ";\n"
    function_body += "\t}\n"

    return function_body


def same_chain(object_id_1: str, object_id_2: str) -> bool:
    return process_blockchain[object_s_process[object_id_1]] == process_blockchain[object_s_process[object_id_2]]


def transfer_and_swap_logic(parent: ET.Element, child: ET.Element, function_code: str, monolithic: bool) -> str:
    identifier = name_or_id(child)

    if "id" in child.attrib:
        child_id = child.attrib["id"]

        if child_id in message_target_to_source.keys():
            source_id = message_target_to_source[child_id]
            source_process_name = clean_string(
                process_names[object_s_process[source_id]])
            target_process_name = clean_string(
                process_names[object_s_process[child_id]])
            if same_chain(child_id, source_id):
                function_code = function_code.replace("$modifiers", "only(" + source_process_name + ")")
            else:
                function_code = function_code.replace("$modifiers", "only(notary)")

            # Assuming that one flow object is the target of only one message flow
            flow_id = message_target_to_flow[child_id]
            flow_name = message_name[flow_id]
            if flow_id in message_action.keys():
                action = message_action[flow_id]
                if "@Transfer" in action:
                    sent = get_sent_token(action)

                    if sent.lower() == "eth":
                        function_code += "\t\trequire(msg.value > 0);\n\n" \
                                         "\t\t\tassert(/*enter further validation code here*/);"
                    else:
                        function_code = "\tbool called_" + identifier + ";\n\tuint lastBalanceFor_" + \
                                        identifier + ";" + function_code
                        function_code += "\t\tif(!called_" + identifier + "){\n" + \
                                         "\t\t\tcalled_" + identifier + " = true;\n" + \
                                         "\t\t\tlastBalanceFor_" + identifier + " = " + sent + \
                                         "_token.balanceOf(address(this));" + \
                                         "\n\t\t}\n" + \
                                         "\t\telse{\n" + \
                                         "\t\t\tcalled_" + identifier + " = false;\n" + \
                                         "\t\t\tassert(lastBalanceFor_" + identifier + " < " + \
                                         sent + "_token.balanceOf(address(this)));\n" \
                                                "\t\t\tassert(/*enter further validation code here*/);" + \
                                         "\t\t}\n\n"
                # If  i m the target i want to check that i actually received the sent amount

                elif "@Swap" in action:
                    sent = get_sent_token(action)
                    received = get_received_token(action)

                    if not same_chain(child_id, source_id):
                        swap_started = "\tevent Swap_Initiated_Notification_" + flow_name + "(bytes32 indexed _contractId);\n\n"
                        swap_started += "\tfunction swap_initiated_notification_" + flow_name + "(bytes32 _contractId) only(notary) public{\n"
                        swap_started += "\t\temit Swap_Initiated_Notification_" + flow_name + "(_contractId);\n"
                        swap_started += "\t}\n\n"
                        function_code = swap_started + function_code
                    elif not monolithic:
                        swap_started = "\tevent Swap_Initiated_Notification_" + flow_name + "(bytes32 indexed _contractId);\n\n"
                        swap_started += "\tfunction swap_initiated_notification_" + flow_name + "(bytes32 _contractId) only(" + source_process_name + ") public{\n"
                        swap_started += "\t\temit Swap_Initiated_Notification_" + flow_name + "(_contractId);\n"
                        swap_started += "\t}\n\n"
                        function_code = swap_started + function_code

                    swap_started = "\tevent Swap_Reciprocated_" + flow_name + "(bytes32 indexed _contractId);\n\n"
                    swap_started += "\tfunction swap_reciprocated_" + flow_name + "(bytes32 _contractId) only(" + target_process_name + ") public{\n"
                    swap_started += "\t\temit Swap_Reciprocated_" + flow_name + "(_contractId);\n"
                    swap_started += "\t}\n\n"
                    function_code = swap_started + function_code


                    function_code = function_code.replace(", $params", ", bytes32 _contractId")
                    function_code = function_code.replace("$params", "bytes32 _contractId")

                    if sent.lower() == "eth":
                        function_code += "\t\trequire(haveContract(_contractId), \"Swap not initiated.\");\n\n"
                        function_code += "\t\t(address sender, address receiver, , , , bool withdrawn , , ) = getContract(_contractId);\n\n"

                    else:
                        function_code += "\t\trequire(haveContractERC20(_contractId), \"Swap not initiated.\");\n\n"
                        function_code += "\t\t(address sender, address receiver, , , , bool withdrawn , , ) = getContractERC20(_contractId);\n\n"

                    function_code += "\t\trequire(sender == " + target_process_name + ");\n"
                    function_code += "\t\trequire(receiver == " + source_process_name + ");\n"
                    function_code += "\t\trequire(withdrawn, \"Swap not carried out successfully.\");\n\n"

                # If  i m the target i want to check that there is a similar htlc smart contract on my chain too
        # if the current node is the source of a message flow then
        elif child_id in message_source_to_target.keys():
            target_process_id = object_s_process[message_source_to_target[child_id]]
            target_process_name = clean_string(process_names[target_process_id])

            target_id = message_source_to_target[child_id]
            source_process_name = clean_string(
                process_names[object_s_process[child_id]])

            function_code = function_code.replace("$modifiers", "only(" + source_process_name + ")")

            # Assuming that one flow object is the source of only one mssage flow
            flow_id = message_source_to_flow[child_id]
            flow_name = message_name[flow_id]
            if flow_id in message_action.keys():
                action = message_action[flow_id]
                if "@Transfer" in action:
                    sent = get_sent_token(action)

                    if sent.lower() == "eth":
                        if same_chain(child_id, target_id):
                            function_code += "\t\trequire(msg.value > 0);\n\n"
                            function_code += "\t\t" + target_process_name + ".transfer(msg.value);\n"
                        else:
                            function_code += "\t\t" + target_process_name + \
                                             ".value(msg.value)" + \
                                             ".call(abi.encodeWithSignature(\"trigger_" + \
                                             object_name[child_id] + \
                                             "()\"));\n\n"
                    else:
                        function_code = function_code.replace("$params", "uint _value")

                        function_code += "\t\trequire(_value > 0);\n\n"

                        if same_chain(child_id, target_id):
                            if monolithic:
                                function_code += "\t\ttrigger_" + object_name[target_id] + "();\n\n"

                                function_code += "\t\t" + sent + "_token" + \
                                                 ".transferFrom(" + source_process_name + "," + target_process_name + ", _value);\n\n"

                                function_code += "\t\ttrigger_" + object_name[target_id] + "();\n\n"
                            else:
                                function_code += "\t\t" + target_process_name + \
                                                 ".call(abi.encodeWithSignature(\"trigger_" + \
                                                 object_name[target_id] + \
                                                 "()\"));\n\n"
                                function_code += "\t\t" + sent + "_token" + \
                                                 ".transferFrom(" + source_process_name + "," + target_process_name + ", _value);\n\n"

                                function_code += "\t\t" + target_process_name + \
                                                 ".call(abi.encodeWithSignature(\"trigger_" + \
                                                 object_name[target_id] + \
                                                 "()\"));\n\n"
                        else:
                            # emit some event
                            event_name = "\tevent Transfer_" + sent + "(address indexed _to);\n\n";
                            function_code = event_name + function_code;
                            function_code += "\t\t" + sent + "_token" + \
                                             ".transferFrom(" + source_process_name + "," + target_process_name + ", _value);\n\n"
                            function_code += "\t\temit Transfer_" + sent + "(" + target_process_id + ");\n"

                    # function_code += "\t\t" + target_process_name + \
                    #                  ".call(abi.encodeWithSignature(\"trigger_" + \
                    #                  object_name[child.attrib["id"]] + \
                    #                  "()\"));\n\n"
                # If  i m the target i want to check that i actually received the sent amount

                elif "@Swap" in action:
                    sent = get_sent_token(action)
                    received = get_received_token(action)

                    if not same_chain(child_id, target_id):
                        swap_started = "\tevent Swap_Reciprocated_Notification_" + flow_name + "(bytes32 indexed _contractId);\n\n"
                        swap_started += "\tfunction swap_reciprocated_notification_" + flow_name + "(bytes32 _contractId) only(notary) public{\n"
                        swap_started += "\t\temit Swap_Reciprocated_Notification_" + flow_name + "(_contractId);\n"
                        swap_started += "\t}\n\n"
                        function_code = swap_started + function_code
                    elif not monolithic:
                        swap_started = "\tevent Swap_Reciprocated_Notification_" + flow_name + "(bytes32 indexed _contractId);\n\n"
                        swap_started += "\tfunction swap_reciprocated_notification_" + flow_name + "(bytes32 _contractId) only(" + target_process_name + ") public{\n"
                        swap_started += "\t\temit Swap_Reciprocated_Notification_" + flow_name + "(_contractId);\n"
                        swap_started += "\t}\n\n"
                        function_code = swap_started + function_code

                    swap_started = "\n\n\tevent Swap_Initiated_" + flow_name + "(bytes32 indexed _contractId);\n\n"
                    swap_started += "\tfunction swap_initiated_" + flow_name + "(bytes32 _contractId) only(" + source_process_name + ") public{\n"
                    swap_started += "\t\temit Swap_Initiated_" + flow_name + "(_contractId);\n"
                    swap_started += "\t}\n\n"
                    function_code = swap_started + function_code

                    function_code = function_code.replace(", $params", ", bytes32 _contractId")
                    function_code = function_code.replace("$params", "bytes32 _contractId")

                    if sent.lower() == "eth":
                        function_code += "\t\trequire(haveContract(_contractId), \"Swap not initiated.\");\n\n"
                        function_code += "\t\t(address sender, address receiver, , , , bool withdrawn , , ) = getContract(_contractId);\n\n"

                    else:
                        function_code += "\t\trequire(haveContractERC20(_contractId), \"Swap not initiated.\");\n\n"
                        function_code += "\t\t(address sender, address receiver, , , , bool withdrawn , , ) = getContractERC20(_contractId);\n\n"

                    function_code += "\t\trequire(sender == " + source_process_name + ");\n"
                    function_code += "\t\trequire(receiver == " + target_process_name + ");\n"
                    function_code += "\t\trequire(withdrawn, \"Swap not carried out successfully.\");\n\n"
            # else:
            # if same_chain(child_id, target_id):
            #     function_code += "\t\t(bool success, ) = " + target_process_name + \
            #                      ".call(abi.encodeWithSignature(\"trigger_" + \
            #                      object_name[message_source_to_target[child.attrib["id"]]] + \
            #                      "()\"));\n"
            #     function_code += "\t\tassert(success);\n\n"

    return function_code


# Input
#       Nada
#
# Output
#       (Solidity smart contract name, Solidity smart contract)
#
# Effects
#       Nada
#
# Description
#       Returns Solidity smart contract that can be used to record all events between the processes involved
#       in a BPMN file.


def bpmn_collab_to_solidity_sc() -> (str, str):
    smart_contract_name = clean_string("_".join(process_names.values()) + "_Collaboration")
    smart_contract = 'contract ' + smart_contract_name + '{\n\n'
    for name in message_name.values():
        event_name = clean_string(name)
        function_name = "trigger_" + event_name
        smart_contract += "\n\n\tevent " + event_name + "(address indexed _from, address indexed _to);\n\n"
        smart_contract += "\tfunction " + function_name + "(address _to) public {\n"
        smart_contract += "\t\temit " + event_name + "(msg.sender, _to);\n"
        smart_contract += "\t}\n\n"
    smart_contract += "}"
    return smart_contract_name, smart_contract


def generate_notary() -> str:
    params = []

    notary = "\tconst Web3 = require('web3')\n"
    notary += "\tconst etjs = require('ethereumjs-tx')\n\n"

    params.append("notaryAddressPrivateKey")
    params.append("notaryAddress")

    chains: set = set()

    for source in communicating_processes.keys():
        targets = communicating_processes[source]
        for target_chain in {process_blockchain[target] for target in targets}:
            if process_blockchain[source] != target_chain:
                chains.add(process_blockchain[source])
                chains.add(target_chain)

    for chain in chains:
        params.append(chain)
        notary += "\tconst web3" + chain + " = new Web3(new Web3.providers.WebsocketProvider(" + chain + "))\n\n"
    ####

    ####
    smart_contracts: set = set()

    cross_chain_flows = {}

    for source_object in message_source_to_target.keys():
        source_process = object_s_process[source_object]
        source_chain = process_blockchain[source_process]

        target_process = object_s_process[message_source_to_target[source_object]]
        target_chain = process_blockchain[target_process]

        if source_chain != target_chain:
            smart_contracts.add(source_process)
            smart_contracts.add(target_process)
            if source_process not in cross_chain_flows.keys():
                cross_chain_flows[source_process] = {target_process}
            else:
                cross_chain_flows[source_process].add(target_process)

    for smart_contract in smart_contracts:
        chain = process_blockchain[smart_contract]
        smart_contract_name = process_names[smart_contract]
        params.append(smart_contract_name + "Address")

        params.append(smart_contract_name + "JSONPath")
        notary += "\tconst " + smart_contract_name + "JSON = require(" + smart_contract_name + "JSONPath" + ")\n"
        notary += "\tconst " + smart_contract_name + " = new web3" + chain + ".eth.Contract(" + smart_contract_name + "JSON.abi, " \
                  + smart_contract_name + "Address)\n"
        notary += "\t" + smart_contract_name + ".setProvider(new Web3.providers.WebsocketProvider(" + chain + "))\n\n"
    ####

    for source_object in message_source_to_target.keys():
        source_process = object_s_process[source_object]
        source_process_name = process_names[source_process]

        target_object = message_source_to_target[source_object]
        target_process = object_s_process[target_object]
        target_process_name = process_names[target_process]

        flow = message_source_to_flow[source_object]
        message = clean_string(message_name[flow])
        triggered_event = clean_string(message)
        target_object_function = "trigger_" + object_name[target_object]

        if process_blockchain[source_process] != process_blockchain[target_process]:
            source_chain = process_blockchain[target_process]

            if flow in message_action.keys() and "@Swap" in message_action[flow]:
                flow_event_name = "Swap_Initiated_" + message

                notary += event_subscriber_code(source_process_name, flow_event_name, target_process_name,
                                                source_chain, "swap_initiated_notification_" + message, "event.args._contractId", "", "")

                flow_event_name_target = "Swap_Reciprocated_" + message

                notary += event_subscriber_code(target_process_name, flow_event_name_target, source_process_name,
                                                target_chain, "swap_reciprocated_notification_" + message, "event.args._contractId", "", "")

            notary += event_subscriber_code(source_process_name, triggered_event, target_process_name,
                                            source_chain, target_object_function, "\"\"", "\"\"", "")

    notary = "function notary(" + ",".join(params) + "){\n" + notary.strip("\n")

    notary += "\n\n\t" + transaction_function().replace("\n", "\n\t")

    notary += "\n}";
    return notary


def event_subscriber_code(source_process_name, triggered_event, target_process_name,
                          source_chain, target_function, target_function_params, action_on_event: str, action_on_succ_call: str) -> str:
    # TODO deal with parameters
    # TODO create javascript function to do transaction sending logic
    notary = "\t" + source_process_name + ".events." + triggered_event + "({})\n"
    notary += "\t\t.on('data', async function(event){\n"
    notary += "\t\t\t" + action_on_event.replace("\n", "\t\t\t\n") + "\n"
    notary += "\t\t\tvar onSuccess = function(){\n" + action_on_succ_call.replace("\n", "\t\t\t\n") + "\n\t\t\t}\n\n"

    notary += "\t\t\ttransaction(" + source_chain + ", web3" + source_chain + ", notaryAddress, notaryAddressPrivateKey, " +\
                                target_process_name + "Address," + target_function + ", " + target_function_params + ", onSuccess)\n"
    notary += "\t\t})\n"
    notary += "\t\t.on('error', console.error)\n\n"

    return notary


def transaction_function() -> str:
    body = "var finishedTransaction = true\n"
    body += "function transaction(chain, web3Chain, sourceAddress, sourcePrivateKey, " + \
                                    "targetAddress, targetFunction, targetFunctionParams, onSuccess){\n"

    body += "\twhile(!finishedTransaction) {}\n"
    body += "\tfinishedTransaction = false\n"
    body += "\tweb3Chain.eth.getTransactionCount(sourceAddress, 'pending', async (err, txCount) => {\n"
    body += "\t\tconst txObject = {\n"
    body += "\t\t\tnonce:    (web3Chain.utils.toHex(txCount)),\n"
    body += "\t\t\tfrom:     sourceAddress,\n"
    body += "\t\t\tto:       targetAddress,\n"
    body += "\t\t\tvalue:    web3Chain.utils.toHex(web3Chain.utils.toWei('0', 'ether')),\n"
    body += "\t\t\tgasLimit: 3000000,\n"
    body += "\t\t\tgasPrice: web3Chain.utils.toHex(await web3Chain.eth.getGasPrice()),\n"
    body += "\t\t\tdata:     targetAddress.methods[targetFunction](targetFunctionParams).encodeABI()\n"
    body += "\t\t}\n"
    body += "\n"
    body += "\t\tconst tx = new etjs.Transaction(txObject, {'chain': 'chain'})\n"
    body += "\t\ttx.sign(Buffer.from(sourcePrivateKey, 'hex'))\n"
    body += "\t\tconst serializedTx = tx.serialize()\n"
    body += "\t\tconst raw = '0x' + serializedTx.toString('hex')\n"
    body += "\t\tweb3Chain.eth.sendSignedTransaction(raw, (err, tx) => {\n"
    body += "\t\t\tif(err){\n"
    body += "\t\t\tconsole.log(error)\n"
    body += "\t\t\t} else{\n"
    body += "\t\t\tconsole.log(tx)\n"
    body += "\t\t\tonSuccess()\n"
    body += "\t\t\tfinishedTransaction = true\n"
    body += "\t\t\t}\n"
    body += "\t\t})\n"
    body += "\t})\n"
    body += "}\n"

    return body


def generate_testing_code(monolithic: bool) -> str:
    # start with a pool of ethereum testnets
    # assign processes to chains randomly, obeying specified conditions
    # (i.e. processes tagged with same chain should be on same testnet)

    # for each process
    ## first get the start event
    ##

    chains = ['mainnet', 'ropsten', 'kovan', 'rinkeby', 'goerli']
    infura_key_template = '\"wss://<chain>.infura.io/ws/v3/9d751b2b65094994a2a54eb45ba083f8\"'

    params = []
    global_vars = []

    global_state= "const Web3 = require('web3')\n"
    global_state += "const etjs = require('ethereumjs-tx')\n\n"

    ## TODO need an address for each process
    params.append("_deployerAddressPrivateKey")
    params.append("_deployerAddress")

    global_vars.append("deployerAddressPrivateKey")
    global_vars.append("deployerAddress")

    body = "\tdeployerAddressPrivateKey = _deployerAddressPrivateKey\n"
    body += "\tdeployerAddress = _deployerAddress\n"

    chain_testnet = {}
    process_testnet = {}
    processes = []
    i = 0

    for process in process_blockchain.keys():
        if process_blockchain[process] in chain_testnet.keys():
            process_testnet[process] = chains[i]
        else:
            chain_testnet[process_blockchain[process]] = chains[i]
            process_testnet[process] = chains[i]
            processes.append(process)
            i += 1

    for testnet in set(process_testnet.values()):
        global_vars.append("web3" + testnet)
        body += "\tweb3" + testnet + " = new Web3(new Web3.providers.WebsocketProvider(" + infura_key_template.replace("<chain>", testnet) + "))\n\n"

    cross_chain_flows = {}

    for source_object in message_source_to_target.keys():
        source_process = object_s_process[source_object]
        source_chain = process_blockchain[source_process]

        target_process = object_s_process[message_source_to_target[source_object]]
        target_chain = process_blockchain[target_process]

        if source_chain != target_chain:
            if source_process not in cross_chain_flows.keys():
                cross_chain_flows[source_process] = {target_process}
            else:
                cross_chain_flows[source_process].add(target_process)


    for process in processes:
        chain = process_testnet[process]
        smart_contract_name = process_names[process]

        params.append(smart_contract_name + "JSONPath")
        body += "\tconst " + smart_contract_name + "JSON = require(" + smart_contract_name + "JSONPath" + ")\n"

        global_vars.append(smart_contract_name)

        body += "\t" + smart_contract_name + " = new web3" + chain + ".eth.Contract(" + smart_contract_name + "JSON.abi)\n"
        body += "\t" + smart_contract_name + ".setProvider(new Web3.providers.WebsocketProvider(" + chain + "))\n\n"

        # deploy, and listen to success, after which the address is saved to variable
        body += "\t" + smart_contract_name + ".deploy({\n"
        body += "\t\tdata: " + smart_contract_name + "JSON.bytecode,\n"
        # TODO need to identify and enter values for constructor arguments
        body += "\t\targuments: []\n"
        body += "\t})\n"
        body += "\t.send({\n"
        body += "\t\tfrom: 'deployerAddress',\n"
        body += "\t\tgasLimit: 3000000,\n"
        body += "\t\tgasPrice: " + smart_contract_name + ".provider.utils.toHex(await (web3" + chain + ".eth.getGasPrice()))\n"
        body += "\t}, function(error, transactionHash){ })\n"
        body += "\t.on('receipt', function(receipt){\n"
        body += "\t\t" + smart_contract_name + "Address = receipt.contractAddress\n"
        body += "\t})\n"
        ## TODO what to do on confirmation?
        body += "\t.on('confirmation', function(confirmationNumber, receipt){  })\n"
        body += "\t.then(function(newContractInstance){\n"
        body += "\t\t" + smart_contract_name + "Address = receipt.contractAddress\n"
        body += "\t\t" + smart_contract_name + " = newContractInstance\n"
        body += "\t});\n"

    body = "function deploy(" + ",".join(params) + "){\n" + body.strip("\n") + "\n}"

    global_state += "\n".join(["var " + global_var for global_var in global_vars])

    body = global_state + "\n\n" + body + "\n\n"

    process_loop_params = []

    process_loop = ""

    # Array of Maps from Process to Array of Nodes
    next_flow_objects = processes_wo_dependencies()

    while len(next_flow_objects.items()) != 0:
        new_next_flow_objects = {}
        for process in next_flow_objects.keys():
            ## TODO to process specific owner address
            source_address = "deployerAddress"
            source_private_key = "deployerPrivateKey"
            for flow_object in next_flow_objects[process]:
                chain_name = process_testnet[name_or_id(process)]

                transaction_params = [chain_name, "web3" + chain_name, source_address, source_private_key,
                                          name_or_id(process), "trigger_" + name_or_id(flow_object), "\"\"", "{}"]

                process_loop += "\t\ttransaction(" + ", ".join(transaction_params) + ")\n"

                next_nodes = [next for next in next(flow_object, process)]

                if process in new_next_flow_objects.keys():
                    new_next_flow_objects[process]\
                            .append(next_nodes)
                else:
                    new_next_flow_objects[process] = next_nodes


        next_flow_objects = new_next_flow_objects

    process_loop = "function process_loop(" + ",".join(process_loop_params) + "){\n" + process_loop.strip("\n") + "\n}"

    body += "\n\n" + process_loop + "\n\n" + transaction_function()

    return body


def processes_wo_dependencies() -> Dict:
    process_event_mapping = {}
    # return processes that have a start event that is not the target of a collaboration flow
    for process in brokers or only_event_processes:
        start_events = [child for child in process if "startEvent" in child.tag]
        for start_event in start_events:
            if start_event not in message_target_to_flow.keys():
                if process in process_event_mapping.keys():
                    process_event_mapping[process].append(start_event)
                else:
                    process_event_mapping[process] = [start_event]

    return process_event_mapping


def colloborative_Flow(node: ET.Element, process: ET.Element) -> (ET.Element, ET.Element):
    process_event_mapping = {}
    # return processes that have a start event that is not the target of a collaboration flow
    for process in brokers or only_event_processes:
        start_events = [child for child in process if "startEvent" in child.tag]
        for start_event in start_events:
            if start_event not in message_target_to_flow.keys():
                if process in process_event_mapping.keys():
                    process_event_mapping[process].append(start_event)
                else:
                    process_event_mapping[process] = [start_event]

    return process_event_mapping


def next(node: ET.Element, process: ET.Element) -> [ET.Element]:
    if "endEvent" in node.tag:
        return []

    next_elems = []
    outgoing_flows = [obj for child in node for obj in process if
                      "outgoing" in child.tag and child.text == obj.attrib["id"]]
    for outgoing_flow in outgoing_flows:
        outgoing_object_ref = outgoing_flow.attrib["targetRef"]
        outgoing_objects = [obj for obj in process if "id" in obj.attrib.keys() and obj.attrib["id"] == outgoing_object_ref]
        next_elems.extend(outgoing_objects)

    return next_elems

# Input
#       node - BPMN object
#
# Output
#       Identifier
#
# Effects
#       Nada
#
# Description
#       Returns name of node it it exists, otherwise the ID of the node, otherwise the text of the node adapted
#       to function as a Solidity identifier.


def name_or_id(node: ET.Element) -> str:
    if "name" in node.attrib.keys():
        return clean_string(node.attrib["name"])
    elif not "id" in node.attrib.keys():
        return clean_string(node.text)
    else:
        return node.attrib["id"]


# Input
#       text - Some string
#
# Output
#       Cleaned text
#
# Effects
#       Nada
#
# Description
#       Adapts input text to function as a Solidity identifier (e.g. "this is some text" -> "this_is_some_text").


def clean_string(text: str) -> str:
    without_whitespace: str = text.strip(" ").strip("\n").replace(" ", "_")
    without_text_in_brackets: str = re.sub(r"\((.*?)\)", "", without_whitespace)
    without_punctuation: str = without_text_in_brackets
    for punct in '''!()-[]{};:'"\,<>./?@#$%^&*~+''':
        without_punctuation = without_punctuation.replace(punct, "")
    return without_punctuation.strip("_").strip("\n")
