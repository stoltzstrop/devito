### definitions pulled out from GenerateXDSL jupyter notebook

from xdsl.dialects.builtin import *
from xdsl.printer import Printer
from devito.ir.ietxdsl import *
from xdsl.dialects.builtin import ModuleOp
from  devito.ir.ietxdsl.operations import Callable
from devito import Grid, TimeFunction, Eq, Operator

from devito.ir.iet.visitors import Visitor

import devito.ir.iet.nodes as nodes

from devito.types.basic import IndexedData
from sympy import Indexed, IndexedBase, symbols, Integer, Symbol, Add, Mul, Eq, Mod

ctx = MLContext()
Builtin(ctx)
iet = IET(ctx)


def add_to_block(expr, arg_by_expr, result):
    if expr in arg_by_expr:
        return
    
    if isinstance(expr, IndexedData):
        # Only index first bit of IndexedData
        add_to_block(expr.args[0], arg_by_expr, result)
        arg_by_expr[expr] = arg_by_expr[expr.args[0]]
        return
    
    if isinstance(expr, Symbol):
        # All symbols must be passed in at the start
        my_expr = Symbol(expr.name)
        assert my_expr in arg_by_expr, f'Symbol with name {expr.name} not found in {arg_by_expr}'
        arg_by_expr[expr] = arg_by_expr[my_expr]
        return
    
    if isinstance(expr, Integer):
        constant = int(expr.evalf())
        arg = Constant.get(constant)
        arg_by_expr[expr] = arg
        result.append(arg)
        return

    for child_expr in expr.args:
        add_to_block(child_expr, arg_by_expr, result)
    
    if isinstance(expr, Add):
        lhs = arg_by_expr[expr.args[0]]
        rhs = arg_by_expr[expr.args[1]]
        sum = Addi.get(lhs, rhs)
        arg_by_expr[expr] = sum
        result.append(sum)
        return

    if isinstance(expr, Mod):
        lhs = arg_by_expr[expr.args[0]]
        rhs = arg_by_expr[expr.args[1]]
        sum = Modi.get(lhs, rhs)
        arg_by_expr[expr] = sum
        result.append(sum)
        return

    if isinstance(expr, Indexed):
        add_to_block(expr.args[0], arg_by_expr, result)
        prev = arg_by_expr[expr.args[0]]
        for child_expr in expr.args[1:]:
            add_to_block(child_expr, arg_by_expr, result)
            child_arg = arg_by_expr[child_expr]
            idx = Idx.get(prev, child_arg)
            result.append(idx)
            prev = idx
        arg_by_expr[expr] = prev
        return
    
    if isinstance(expr, Eq):
        add_to_block(expr.args[0], arg_by_expr, result)
        lhs = arg_by_expr[expr.args[0]]
        add_to_block(expr.args[1], arg_by_expr, result)
        rhs = arg_by_expr[expr.args[1]]
        assign = Assign.build([lhs, rhs])
        arg_by_expr[expr] = assign
        result.append(assign)
        return

    assert False, f'unsupported expr {expr} of type {expr.func}'

def myVisit(node, block=None, ctx={}):
    assert isinstance(node, nodes.Node), f'Argument must be subclass of Node, found: {node}'
    
    if hasattr(node, 'is_Callable') and node.is_Callable:
        name = node.name
        parameters = node.parameters
        body = myVisit(node.body)
        return
    
    if isinstance(node, nodes.CallableBody):
#         print(f'CallableBody: f{node.view}')
        body = [myVisit(x) for x in node.body]
        return 
    
    if isinstance(node, nodes.Expression):
        expr = node.expr
        r = []
        add_to_block(expr, {Symbol(s): a for s, a in ctx.items()}, r)
        block.add_ops(r)
        return
    
    if isinstance(node, nodes.ExpressionBundle):
        assert len(node.children) == 1
        assert len(node.children[0]) == 1
        myVisit(node.children[0][0], block, ctx)
        return
    
    if isinstance(node, nodes.Iteration):
        assert len(node.children) == 1
        assert len(node.children[0]) == 1
        index = node.index
        b = Block.from_arg_types([iet.i32])
        ctx = {**ctx, index: b.args[0]}
#       TODO: assert(uindices are not empty and are modulo)
        for uindex in list(node.uindices):
            r = []
            add_to_block(uindex.symbolic_min,{Symbol(s): a for s, a in ctx.items()}, r)
            tmp = uindex.name
            init = Initialise.get(r[-1].results[0],[iet.i32],uindex.name)
            b.add_ops(r)
            b.add_ops([init])
        myVisit(node.children[0][0], b, ctx)
        iteration = Iteration.get(node.properties, node.limits, node.index, b)
        block.add_ops([iteration])
        return

    if isinstance(node, nodes.Section):
        assert len(node.children) == 1
        assert len(node.children[0]) == 1
        myVisit(node.children[0][0], block, ctx)
        return

    if isinstance(node, nodes.TimedList):
        assert len(node.children) == 1
        assert len(node.children[0]) == 1
        myVisit(node.children[0][0], block, ctx)
        return

    raise TypeError(f'Unsupported type of node: {type(node)}, {vars(node)}')

