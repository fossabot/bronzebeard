from ctypes import c_uint32
from functools import partial
import re
import struct
import sys


REGISTERS = {
    'x0': 0, 'zero': 0,
    'x1': 1, 'ra': 1,
    'x2': 2, 'sp': 2,
    'x3': 3, 'gp': 3,
    'x4': 4, 'tp': 4,
    'x5': 5, 't0': 5,
    'x6': 6, 't1': 6,
    'x7': 7, 't2': 7,
    'x8': 8, 's0': 8, 'fp': 8,
    'x9': 9, 's1': 9,
    'x10': 10, 'a0': 10,
    'x11': 11, 'a1': 11,
    'x12': 12, 'a2': 12,
    'x13': 13, 'a3': 13,
    'x14': 14, 'a4': 14,
    'x15': 15, 'a5': 15,
    'x16': 16, 'a6': 16,
    'x17': 17, 'a7': 17,
    'x18': 18, 's2': 18,
    'x19': 19, 's3': 19,
    'x20': 20, 's4': 20,
    'x21': 21, 's5': 21,
    'x22': 22, 's6': 22,
    'x23': 23, 's7': 23,
    'x24': 24, 's8': 24,
    'x25': 25, 's9': 25,
    'x26': 26, 's10': 26,
    'x27': 27, 's11': 27,
    'x28': 28, 't3': 28,
    'x29': 29, 't4': 29,
    'x30': 30, 't5': 30,
    'x31': 31, 't6': 31,
}


def resolve_register(reg):
    # check if register corresponds to a valid name
    if reg in REGISTERS:
        reg = REGISTERS[reg]

    # ensure register is a number
    try:
        reg = int(reg)
    except ValueError:
        raise ValueError('Register is not a number or valid name: {}'.format(reg))

    # ensure register is between 0 and 31
    if reg < 0 or reg > 31:
        raise ValueError('Register must be between 0 and 31: {}'.format(reg))

    return reg


def r_type(rd, rs1, rs2, opcode, funct3, funct7):
    rd = resolve_register(rd)
    rs1 = resolve_register(rs1)
    rs2 = resolve_register(rs2)

    code = 0
    code |= opcode
    code |= rd << 7
    code |= funct3 << 12
    code |= rs1 << 15
    code |= rs2 << 20
    code |= funct7 << 25

    return struct.pack('<I', code)


def i_type(rd, rs1, imm, opcode, funct3):
    rd = resolve_register(rd)
    rs1 = resolve_register(rs1)

    if imm < -0x800 or imm > 0x7ff:
        raise ValueError('12-bit immediate must be between -0x800 (-2048) and 0x7ff (2047): {}'.format(imm))

    imm = c_uint32(imm).value & 0b111111111111

    code = 0
    code |= opcode
    code |= rd << 7
    code |= funct3 << 12
    code |= rs1 << 15
    code |= imm << 20

    return struct.pack('<I', code)


def s_type(rs1, rs2, imm, opcode, funct3):
    rs1 = resolve_register(rs1)
    rs2 = resolve_register(rs2)

    if imm < -0x800 or imm > 0x7ff:
        raise ValueError('12-bit immediate must be between -0x800 (-2048) and 0x7ff (2047): {}'.format(imm))

    imm = c_uint32(imm).value & 0b111111111111

    imm_11_5 = (imm >> 5) & 0b1111111
    imm_4_0 = imm & 0b11111

    code = 0
    code |= opcode
    code |= imm_4_0 << 7
    code |= funct3 << 12
    code |= rs1 << 15
    code |= rs2 << 20
    code |= imm_11_5 << 25

    return struct.pack('<I', code)


def b_type(rs1, rs2, imm, opcode, funct3):
    rs1 = resolve_register(rs1)
    rs2 = resolve_register(rs2)

    if imm < -0x1000 or imm > 0x0fff:
        raise ValueError('12-bit multiple of 2 immediate must be between -0x1000 (-4096) and 0x0fff (4095): {}'.format(imm))
    if imm % 2 == 1:
        raise ValueError('12-bit multiple of 2 immediate must be a muliple of 2: {}'.format(imm))

    imm = imm // 2
    imm = c_uint32(imm).value & 0b111111111111

    imm_12 = (imm >> 11) & 0b1
    imm_11 = (imm >> 10) & 0b1
    imm_10_5 = (imm >> 4) & 0b111111
    imm_4_1 = imm & 0b1111

    code = 0
    code |= opcode
    code |= imm_11 << 7
    code |= imm_4_1 << 8
    code |= funct3 << 12
    code |= rs1 << 15
    code |= rs2 << 20
    code |= imm_10_5 << 25
    code |= imm_12 << 31

    return struct.pack('<I', code)


def u_type(rd, imm, opcode):
    rd = resolve_register(rd)

    if imm < -0x80000 or imm > 0x7ffff:
        raise ValueError('20-bit immediate must be between -0x80000 (-524288) and 0x7ffff (524287): {}'.format(imm))

    imm = c_uint32(imm).value & 0b11111111111111111111

    code = 0
    code |= opcode
    code |= rd << 7
    code |= imm << 12

    return struct.pack('<I', code)


def j_type(rd, imm, opcode):
    rd = resolve_register(rd)

    if imm < -0x100000 or imm > 0x0fffff:
        raise ValueError('20-bit multiple of 2 immediate must be between -0x100000 (-1048576) and 0x0fffff (1048575): {}'.format(imm))
    if imm % 2 == 1:
        raise ValueError('20-bit multiple of 2 immediate must be a muliple of 2: {}'.format(imm))

    imm = imm // 2
    imm = c_uint32(imm).value & 0b11111111111111111111

    imm_20 = (imm >> 19) & 0b1
    imm_19_12 = (imm >> 11) & 0b11111111
    imm_11 = (imm >> 10) & 0b1
    imm_10_1 = imm & 0b1111111111

    code = 0
    code |= opcode
    code |= rd << 7
    code |= imm_19_12 << 12
    code |= imm_11 << 20
    code |= imm_10_1 << 21
    code |= imm_20 << 31

    return struct.pack('<I', code)


LUI = partial(u_type, opcode=0b0110111)
AUIPC = partial(u_type, opcode=0b0010111)
JAL = partial(j_type, opcode=0b1101111)
JALR = partial(i_type, opcode=0b1100111, funct3=0b000)
BEQ = partial(b_type, opcode=0b1100011, funct3=0b000)
BNE = partial(b_type, opcode=0b1100011, funct3=0b001)
BLT = partial(b_type, opcode=0b1100011, funct3=0b100)
BGE = partial(b_type, opcode=0b1100011, funct3=0b101)
BLTU = partial(b_type, opcode=0b1100011, funct3=0b110)
BGEU = partial(b_type, opcode=0b1100011, funct3=0b111)
LB = partial(i_type, opcode=0b0000011, funct3=0b000)
LH = partial(i_type, opcode=0b0000011, funct3=0b001)
LW = partial(i_type, opcode=0b0000011, funct3=0b010)
LBU = partial(i_type, opcode=0b0000011, funct3=0b100)
LHU = partial(i_type, opcode=0b0000011, funct3=0b101)
SB = partial(s_type, opcode=0b0100011, funct3=0b000)
SH = partial(s_type, opcode=0b0100011, funct3=0b001)
SW = partial(s_type, opcode=0b0100011, funct3=0b010)
ADDI = partial(i_type, opcode=0b0010011, funct3=0b000)
SLTI = partial(i_type, opcode=0b0010011, funct3=0b010)
SLTIU = partial(i_type, opcode=0b0010011, funct3=0b011)
XORI = partial(i_type, opcode=0b0010011, funct3=0b100)
ORI = partial(i_type, opcode=0b0010011, funct3=0b110)
ANDI = partial(i_type, opcode=0b0010011, funct3=0b111)
SLLI = partial(r_type, opcode=0b0010011, funct3=0b001, funct7=0b0000000)
SRLI = partial(r_type, opcode=0b0010011, funct3=0b101, funct7=0b0000000)
SRAI = partial(r_type, opcode=0b0010011, funct3=0b101, funct7=0b0100000)
ADD = partial(r_type, opcode=0b0110011, funct3=0b000, funct7=0b0000000)
SUB = partial(r_type, opcode=0b0110011, funct3=0b000, funct7=0b0100000)
SLL = partial(r_type, opcode=0b0110011, funct3=0b001, funct7=0b0000000)
SLT = partial(r_type, opcode=0b0110011, funct3=0b010, funct7=0b0000000)
SLTU = partial(r_type, opcode=0b0110011, funct3=0b011, funct7=0b0000000)
XOR = partial(r_type, opcode=0b0110011, funct3=0b100, funct7=0b0000000)
SRL = partial(r_type, opcode=0b0110011, funct3=0b101, funct7=0b0000000)
SRA = partial(r_type, opcode=0b0110011, funct3=0b101, funct7=0b0100000)
OR = partial(r_type, opcode=0b0110011, funct3=0b110, funct7=0b0000000)
AND = partial(r_type, opcode=0b0110011, funct3=0b111, funct7=0b0000000)

R_TYPE_INSTRUCTIONS = {
    'slli': SLLI,
    'srli': SRLI,
    'srai': SRAI,
    'add': ADD,
    'sub': SUB,
    'sll': SLL,
    'slt': SLT,
    'sltu': SLTU,
    'xor': XOR,
    'srl': SRL,
    'sra': SRA,
    'or': OR,
    'and': AND,
}

I_TYPE_INSTRUCTIONS = {
    'jalr': JALR,
    'lb': LB,
    'lh': LH,
    'lw': LW,
    'lbu': LBU,
    'lhu': LHU,
    'addi': ADDI,
    'slti': SLTI,
    'sltiu': SLTIU,
    'xori': XORI,
    'ori': ORI,
    'andi': ANDI,
}

S_TYPE_INSTRUCTIONS = {
    'sb': SB,
    'sh': SH,
    'sw': SW,
}

B_TYPE_INSTRUCTIONS = {
    'beq': BEQ,
    'bne': BNE,
    'blt': BLT,
    'bge': BGE,
    'bltu': BLTU,
    'bgeu': BGEU,
}

U_TYPE_INSTRUCTIONS = {
    'lui': LUI,
    'auipc': AUIPC,
}

J_TYPE_INSTRUCTIONS = {
    'jal': JAL,
}

INSTRUCTIONS = {}
INSTRUCTIONS.update(R_TYPE_INSTRUCTIONS)
INSTRUCTIONS.update(I_TYPE_INSTRUCTIONS)
INSTRUCTIONS.update(S_TYPE_INSTRUCTIONS)
INSTRUCTIONS.update(B_TYPE_INSTRUCTIONS)
INSTRUCTIONS.update(U_TYPE_INSTRUCTIONS)
INSTRUCTIONS.update(J_TYPE_INSTRUCTIONS)

# definitions for the "items" that can be found in an assembly program
#   name: str
#   rd, rs1, rs2: int, str
#   imm: int, Position, Offset, Hi, Lo
#   alignment: int
#   data: str, bytes
#   format: str
#   value: int
#   label: str
RTypeInstruction = namedtuple('RTypeInstruction', 'name rd rs1 rs2')
ITypeInstruction = namedtuple('ITypeInstruction', 'name rd rs1 imm')
STypeInstruction = namedtuple('STypeInstruction', 'name rs1 rs2 imm')
BTypeInstruction = namedtuple('BTypeInstruction', 'name rs1 rs2 imm')
UTypeInstruction = namedtuple('UTypeInstruction', 'name rd imm')
JTypeInstruction = namedtuple('JTypeInstruction', 'name rd imm')
Label = namedtuple('Label', 'name')
Align = namedtuple('Align', 'alignment')
Blob = namedtuple('Blob', 'data')
Pack = namedtuple('Pack', 'fmt imm')
Position = namedtuple('Position', 'label value')
Offset = namedtuple('Offset', 'label')
Hi = namedtuple('Hi', 'value')
Lo = namedtuple('Lo', 'value')

# Passes (labels, position):
# 1. Resolve aligns  (convert aligns to blobs based on position)
# 2. Resolve labels  (store label locations into dict)
# 3. Resolve immediates  (resolve refs to labels, error if not found, leaves integers)
# 4. Resolve relocations  (resolve Hi / Lo relocations)
# 5. Assemble!  (convert everything to bytes)

def sign_extend(value, bits):
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)

def relocate_hi(imm):
    if imm & 0x800:
        imm += 2**12
    return sign_extend((imm >> 12) & 0x000fffff, 20)

def relocate_lo(imm):
    return sign_extend(imm & 0x00000fff, 12)

def lex_assembly(assembly):
    # strip comments
    assembly = re.sub(r'#.*?$', r'', assembly, flags=re.MULTILINE)

    # split into lines
    lines = assembly.splitlines()

    # strip whitespace
    lines = [line.strip() for line in lines]

    # skip empty lines
    lines = [line for line in lines if len(line) > 0]

    # split lines into tokens
    items = [re.split(r'[\s,()]+', line) for line in lines]

    # remove empty tokens
    for item in items:
        while '' in item:
            item.remove('')

    return items

def parse_assembly(items):
    def parse_immediate(imm, context):
        if imm[0] == 'position':
            label = imm[1]
            expr = imm[2:]
            return Position(label, eval(expr, context))
        elif imm[0] == 'offset':
            label = imm[1]
            return Offset(label)
        elif imm[0] == '%hi':
            expr = ' '.join(imm[1:])
            return Hi(eval(expr, context))
        elif imm[0] == '%lo':
            expr = ' '.join(imm[1:])
            return Lo(eval(expr, context))
        else:
            return int(imm[0])

    context = {}

    program = []
    for item in items:
        # labels
        if len(item) == 1 and item[0].endswith(':'):
            label = item[0]
            label = label.rstrip(':')
            program.append(Label(label))
        # variable assignment
        elif len(item) >= 3 and item[1] == '=':
            name, _, *expr = item
            expr = ' '.join(expr)
            context[name] = eval(expr)
        # blobs
        elif item[0].lower() == 'blob':
            data = item[1]
            data = data.encode()
            program.append(Blob(data))
        # packs
        elif item[0].lower() == 'pack':
            fmt = item[1]
            imm = parse_immediate(item[2:])
            program.append(Pack(fmt, imm))
        # r-type instructions
        elif item[0].lower() in R_TYPE_INSTRUCTIONS:
            pass
        else:
            raise SystemExit('invalid item:', ' '.join(item))

    return program

def resolve_aligns(program):
    position = 0
    output = []

    for item in program:
        if type(item) == Align:
            padding = item.alignment - (position % item.alignment)
            if padding == item.alignment:
                continue
            position += padding
            output.append(Blob(b'\x00' * padding))
        elif type(item) == Blob:
            position += len(item.data)
            output.append(item)
        elif type(item) == Pack:
            position += struct.calcsize(item.fmt)
            output.append(item)
        else:
            position += 4
            output.append(item)

    return output

def resolve_labels(program):
    position = 0
    output = []
    labels = {}

    for item in program:
        if type(item) == Label:
            labels[item.name] = position
        else:
            position += len(item)
            output.append(item)

    return output, labels

def resolve_immediates(program, labels):
    position = 0
    output = []

    immediates = [
        ITypeInstruction,
        STypeInstruction,
        BTypeInstruction,
        UTypeInstruction,
        JTypeInstruction,
        Pack,
    ]

    # TODO: way too ugly
    for item in program:
        if type(item) in immediates:
            imm = item.imm
            if type(imm) == Position:
                dest = labels[imm.label]
                base = imm.base
                item.imm = dest + base
            elif type(imm) == Offset:
                dest = labels[imm.label]
                item.imm = dest - position
            elif type(imm) in [Hi, Lo]:
                imm = item.imm.imm
                if type(imm) == Position:
                    dest = labels[imm.label]
                    base = imm.base
                    item.imm.imm = dest + base
                elif type(imm) == Offset:
                    dest = labels[imm.label]
                    item.imm.imm = dest - position

        position += len(item)
        output.append(item)

    return output

def resolve_relocations(program):
    output = []

    immediates = [
        ITypeInstruction,
        STypeInstruction,
        BTypeInstruction,
        UTypeInstruction,
        JTypeInstruction,
        Pack,
    ]

    for item in program:
        if type(item) in immediates:
            if type(item.imm) == Hi:
                item.imm = relocate_hi(item.imm.imm)
            elif type(item.imm) == Lo:
                item.imm = relocate_lo(item.imm.imm)

        output.append(item)

    return output

def assemble(program):
    output = b''

    for item in program:
        output += bytes(item)

    return output


if __name__ == '__main__':
    if len(sys.argv) != 3:
        usage = 'usage: python -m bronzebeard.asm <input_asm> <output_bin>'
        raise SystemExit(usage)

    input_asm = sys.argv[1]
    output_bin = sys.argv[2]

    with open(input_asm) as f:
        assembly = f.read()

    items = lex_assembly(assembly)
    prog = parse_assembly(items)

    from pprint import pprint
    pprint(prog)
