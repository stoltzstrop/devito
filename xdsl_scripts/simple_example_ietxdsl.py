### continuation of xdsl generated code pulled out from GenerateXDSL jupyter notebook
import cgen as cgen
from xdsl.dialects.builtin import *
from xdsl.printer import Printer
from devito.ir.ietxdsl import *
from xdsl.dialects.builtin import ModuleOp
from  devito.ir.ietxdsl.operations import Callable
from devito import Grid, TimeFunction, Eq, Operator

from devito.ir.iet.visitors import Visitor

import devito.ir.iet.nodes as nodes

from devito.types.basic import IndexedData

from xdsl_scripts import ietxdsl_functions


def createStatement(initial_string, val):
    ret_str = initial_string
    if isinstance(val, tuple):
        for t in val:
            ret_str = ret_str + " " + t
    else:
        ret_str = ret_str + " "+ val

    return ret_str


ctx = MLContext()
Builtin(ctx)
iet = IET(ctx)

grid = Grid(shape = (3, 3))
u = TimeFunction(name='u', grid=grid)
eq = Eq(u.forward, u + 1)
op = Operator([eq])

#expr = op.body.body[1].body[0].children[0][0].body[0].body[0].children[0][0].children[0][0].children[0][0].expr
#print(expr)

# this must be listed later or it causes issues with the op declaration
from sympy import Indexed, IndexedBase, symbols, Integer, Symbol, Add, Mul, Eq

# later in cgeneration those parameters without associate types aren't printed in the Kernel header
op_params = list(op.parameters)
op_types = []
op_header_params = []
for opi in op_params:
    op_types.append(opi._C_typedata)
    op_header_params.append(opi)

# TODO: u also does not get the right name or type and must be passed in this way for now
op_header_params[0] = str(op_header_params[0]._C_symbol)
op_types[0] = str(op_params[0]._C_typename)

# TODO: we still need to add "t0" and "t1" even though they aren't passed in
op_params.append("t0")
op_params.append("t1")
# TODO: also have to fix u:
op_params[0] = "u"


ints = []
for opi in op_params:
    ints.append(str(opi))

b = Block.from_arg_types([iet.i32] * len(ints))
d = {name: register for name, register in zip(ints, b.args)}

# body of kernel
node = op.body.body[1].body[0].children[0][0].body[0].body[0]
kernel = op.body

headers = op._headers
includes = op._includes
struct_decs = [i._C_typedecl for i in op.parameters if i._C_typedecl is not None]
test : cgen.Struct = struct_decs[0]
kernel_comments = op.body.body[0]
uvec_cast =op.body.args.get('casts')[0]
full_loop = op.body.body[1].args.get('body')[0]
#print(vars(node))

#header_result = ietxdsl_functions.myVisit(nodes.Element(cgen.Statement(('#define',)+headers[0])), block=headers_b, ctx=headers_d)
#include_result = ietxdsl_functions.myVisit(includes, block=b, ctx=d)

comment_result = ietxdsl_functions.myVisit(kernel_comments, block=b, ctx=d)
uvec_result = ietxdsl_functions.myVisit(uvec_cast, block=b, ctx=d)
main_result = ietxdsl_functions.myVisit(full_loop, block=b, ctx=d)

Printer()._print_named_block(b)
call_obj = Callable.get("kernel", ints, op_header_params, op_types, b)
Printer().print_op(ModuleOp.from_region_or_ops([call_obj]))
cgen = CGeneration()


# TODO: is there a more formal way to do this?
# print headers:
for header in headers:
    cgen.printOperation(Statement.get(createStatement("#define",header)))
# print includes:
for include in includes:
    cgen.printOperation(Statement.get(createStatement("#include",include)))
# print structs:
for struct in struct_decs:
    cgen.printOperation(StructDecl.get(struct.tpname, struct.fields, struct.declname, struct.pad_bytes))

# print Kernel
cgen.printCallable(call_obj)

print(cgen.str())

#Printer()._print_named_block(b)
