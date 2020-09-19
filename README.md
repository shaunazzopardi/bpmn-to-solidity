# bpmn-to-solidity
A parser from BPMN to Solidity smart contracts, possibly deployed on different blockchains.

# Description

This prototype takes a BPMN file and compiles it into a number of smart contracts. BPMN pools maybe annotated with different blockchain identifiers, signifiying that the pool's process will be executed on that blockchain. Flows between pools may be: (i) message transfers; (ii) token transfers; or (iii) token swaps. See the case studies in ''./case-studies'' (visualise at demo.bpmn.io) as an example.

# Limitations

This is a proof of concept. Only a subset of BPMN can be currently handled. Currently we do not have a list of limitations. 

# Usage

1. Compile python project.
2. Run with parameters: ```-i <path to input .bpmn file> -o <path to output directory> --mult_chain_mode <true or false>```
  
