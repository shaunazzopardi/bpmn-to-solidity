import sys
import getopt
from bpmnparser import produce_solidity_from_bpmn


def main():
    bpmnfile = ''
    outdir = ''
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:o:", ["ibpmn=", "odir=","i=", "o="])
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
    produce_solidity_from_bpmn(bpmnfile, outdir)


if __name__ == "__main__":
    main()
