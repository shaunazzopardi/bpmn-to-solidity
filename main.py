import sys
import getopt
from bpmn_parser import produce_solidity_from_bpmn


def main():
    bpmnfile = ''
    outdir = ''
    mult_chain_mode = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:o:", ["ibpmn=", "odir=","i=", "o=", "mult_chain_mode="])
    except getopt.GetoptError:
        print
        'main.py -i <bpmnfile> -o <outdir>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print
            'test.py -i <bpmnfile> -o <outdir>'
            sys.exit()
        elif opt in ("-i", "--ibpmn"):
            bpmnfile = arg
        elif opt in ("-o", "--odir"):
            outdir = arg
        elif opt in ("--mult_chain_mode"):
            if arg.lower() == "true":
                mult_chain_mode = True
    produce_solidity_from_bpmn(bpmnfile, outdir, mult_chain_mode)


if __name__ == "__main__":
    main()
