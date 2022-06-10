### continuation of xdsl generated code pulled out from GenerateXDSL jupyter notebook

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

# TODO get parameters and their types this way --
# TODO add corresponding attribute in operations.Callable for types
# TODO then maybe in cgen those parameters without associate types aren't printed in the Kernel header
op_params = list(op.parameters) # should get list of parameters this way
tmp = op_params[0]._C_typedata
tmp2 = op_params[1]._C_typedata
tmp3 = op_params[7]._C_typedata
# TODO: but for now we still need to add "t0" and "t1" even though they aren't passed in
ints  = ['u', 'time_M', 'time_m', 'x_M', 'x_m', 'y_M', 'y_m', 'timers','t0','t1']

b = Block.from_arg_types([iet.i32] * len(ints))
d = {name: register for name, register in zip(ints, b.args)}
    
#body of kernel
node = op.body.body[1].body[0].children[0][0].body[0].body[0]
full_loop = op.body.body[1].args.get('body')[0]
kernel = op.body
kernel_comments = op.body.body[0]
#print(vars(node))

result =  ietxdsl_functions.myVisit(full_loop, block=b, ctx=d)
#result =  ietxdsl_functions.myVisit(node, block=b, ctx=d)

Printer()._print_named_block(b)
call_obj = Callable.get("kernel", ints,b)
Printer().print_op(ModuleOp.from_region_or_ops([call_obj]))
cgen = CGeneration()
cgen.printCallable(call_obj)

print(cgen.str())

#Printer()._print_named_block(b)
