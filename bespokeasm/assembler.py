from line_parser import LineParser

class Assembler:

    def __init__(self, source_file):
        self.source_file = source_file

    def assemble_bytecode(self):

        line_obs = []
        with open(self.source_file, 'r') as f:
            line_num = 0
            for  line in f:
                line_num += 1
                line_str = line.strip()
                if len(line_str) > 0:
                    line_obs.append(LineParser(line_str, line_num))

        for l in line_obs:
            print(l)