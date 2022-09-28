import io
from typing import Dict

from devito.ir.ietxdsl.operations import (Callable, Addi, Modi, StructDecl, Statement,
                                          Iteration, IterationWithSubIndices, Assign,
                                          PointerCast, Idx, Initialise, List, Constant,
                                          Powi, Muli)
from devito.tools import flatten
from xdsl.ir import SSAValue, BlockArgument

SSAValueNames: Dict[SSAValue, str] = {}


class CGeneration:

    def __init__(self):
        self.output = io.StringIO()
        self.indentation = 0
        self.iterator_names = {}

    def str(self):
        s = self.output.getvalue()
        self.output.close()
        return s

    def indent(self):
        self.indentation += 2

    def dedent(self):
        self.indentation -= 2

    def print(self, *args, **kwargs):

        if 'indent' in kwargs.keys():
            indent = kwargs.pop('indent')
        else:
            indent = True

        if indent:
            print(" " * self.indentation, file=self.output, end='')

        print(*args, file=self.output, **kwargs)

    # To translate code such as:
    #
    #   cst42 := iet.constant(42)
    #   cst3 := iet.constant(3)
    #   iet.addi(cst42, cst3)
    #
    # into a single-line expression such as:
    #
    #   42 + 3
    #
    # we look at the very last operation in the module and then walk iand
    # recursively print the following tree expressed by the def-use chain of
    # these operations.
    def printModule(self, module):
        # Get the last operation in the module
        self.printOperation(module.ops[-1])

    def printCallable(self, callable_op: Callable):
        arglist = callable_op.body.blocks[0].args

        # print kernels and arguments
        self.print("int Kernel(", end='', indent=False)
        for i, arg in enumerate(arglist):
            SSAValueNames[arg] = callable_op.parameters.data[i].data
        # TODO: fix this workaround
        # need separate loop because only header parameters have types
        for n, op_type in enumerate(callable_op.types.data):
            self.print(op_type.data, end=' ', indent=False)
            self.print(callable_op.header_parameters.data[n].data,
                       end='',
                       indent=False)
            if n < (len(list(callable_op.types.data)) - 1):
                self.print(",", end='', indent=False)

        self.print("){")
        self.indent()
        for each_op in callable_op.body.ops:
            self.printOperation(each_op)
        self.print("return 0;")
        self.dedent()
        self.print("}")
        pass

    def printIteration(self, iteration_op: Iteration):
        # not used?
        ssa_val = iteration_op.body.blocks[0].args[0]
        iterator = str(iteration_op.arg_name.data)
        SSAValueNames[ssa_val] = iterator
        self.iterator_names[
            iteration_op.regions[0].blocks[0].args[0]] = iterator
        lower_bound = iteration_op.limits.data[0].data
        upper_bound = iteration_op.limits.data[1].data
        increment = iteration_op.limits.data[2].data
        self.print(f"for (int {iterator} = {lower_bound}; ", end='')
        self.print(f"{iterator} <= {upper_bound}; ", end='', indent=False)
        self.print(f"{iterator} += {increment}) ", indent=False)
        self.print("{")
        self.indent()
        for op in iteration_op.body.ops:
            if isinstance(op, Iteration) | isinstance(op, Statement) | \
                    isinstance(op, Assign) | isinstance(op, Initialise):
                self.printOperation(op)
        self.dedent()
        self.print("}")
        pass

    def printIterationWithSubIndices(self,
                                     iteration_op: IterationWithSubIndices):
        uindices_names = iteration_op.uindices_names
        uindices_symbmins_divisors = iteration_op.uindices_symbmins_divisors
        uindices_symbmins_dividends = iteration_op.uindices_symbmins_dividends
        ssa_val = iteration_op.body.blocks[0].args[0]
        iterator = "i_" + str(len(self.iterator_names))
        iterator = str(iteration_op.arg_name.data)
        SSAValueNames[ssa_val] = iterator
        self.iterator_names[
            iteration_op.regions[0].blocks[0].args[0]] = iterator
        lower_bound = iteration_op.limits.data[0].data
        upper_bound = iteration_op.limits.data[1].data
        increment = iteration_op.limits.data[2].data
        self.print(f"for (int {iterator} = {lower_bound}, ", end='')

        # initialise subindices

        for i, u in enumerate(uindices_names.data):
            self.print(
                f"{u.data} = ({uindices_symbmins_dividends.data[i].data})%"
                f"({uindices_symbmins_divisors.data[i].data})",
                end='')
            if i < (len(uindices_names.data) - 1):
                self.print(",", end='')
            else:
                self.print(";", end=' ')

        self.print(f"{iterator} <= {upper_bound}; ", end='', indent=False)
        self.print(f"{iterator} += {increment}, ", end='')

        # also increment subindices
        for i, u in enumerate(uindices_names.data):
            self.print(
                f"{u.data} = ({uindices_symbmins_dividends.data[i].data})"
                f"%({uindices_symbmins_divisors.data[i].data})",
                end='')
            if i < (len(uindices_names.data) - 1):
                self.print(",", end='')

        self.print(")", end='')
        self.print("{")
        self.indent()
        self.printOperation(iteration_op.body.ops)
        self.dedent()
        self.print("}")
        pass

    def printResult(self, result):
        if isinstance(result, BlockArgument):
            name = SSAValueNames[result]
            self.print(name, indent=False, end="")
            return
        if isinstance(result, SSAValue):
            self.printOperation(result.op)

    def printOperation(self, operation):
        if isinstance(operation, BlockArgument):
            # Not currently used
            self.print("uuu", indent=False, end="")
            return
        if (isinstance(operation, List)):
            for op in operation:
                if isinstance(op, (Constant, Addi, Idx, Modi)):
                    continue
                self.printOperation(op)
            return

        if (isinstance(operation, Constant)):
            self.print(operation.value.parameters[0].data,
                       indent=False,
                       end='')
            return

        if (isinstance(operation, Addi)):
            self.printResult(operation.input1)
            self.print(" + ", end='', indent=False)
            self.printResult(operation.input2)
            return

        if (isinstance(operation, Modi)):
            self.print("(", end="", indent=False)
            self.printResult(operation.input1)
            self.print(")", end="", indent=False)
            self.print(" % ", end='', indent=False)
            self.print("(", end="", indent=False)
            self.printResult(operation.input2)
            self.print(")", end="", indent=False)
            return

        if (isinstance(operation, Powi)):
            self.print("pow(", end="", indent=False)
            self.print("(", end="", indent=False)
            self.printResult(operation.base)
            self.print(")", end="", indent=False)
            self.print(",", end='', indent=False)
            self.print("(", end="", indent=False)
            self.printResult(operation.exponent)
            self.print(")", end="", indent=False)
            self.print(")", end="", indent=False)
            return

        if (isinstance(operation, Muli)):
            self.printResult(operation.input1)
            self.print(" * ", end='', indent=False)
            self.printResult(operation.input2)
            return

        if (isinstance(operation, Callable)):
            self.printCallable(operation)
            return

        if (isinstance(operation, IterationWithSubIndices)):
            self.printIterationWithSubIndices(operation)
            return

        if (isinstance(operation, Iteration)):
            self.printIteration(operation)
            return

        if (isinstance(operation, Assign)):
            self.print("", end="")
            self.printResult(operation.lhs)
            self.print(" = ", indent=False, end="")
            self.printResult(operation.rhs)
            self.print(";", indent=False)
            return

        if (isinstance(operation, Initialise)):
            results = flatten(operation.results)
            assert len(results) == 1
            type = results[0].typ.name
            # rename float accordingly if required
            if type == "f32":
                type = "float"
            if type == "f64":
                type = "double"
            self.print(type, indent=True, end=" ")

            assignee = operation.id.data
            self.print(assignee, indent=False, end="")
            ssa_val = operation.lhs
            SSAValueNames[ssa_val] = assignee

            self.print(" = ", indent=False, end="")
            self.printResult(operation.rhs)
            self.print(";", indent=False)
            return

        if (isinstance(operation, Idx)):
            self.printResult(operation.array)
            self.print("[", indent=False, end="")
            self.printResult(operation.index)
            self.print("]", indent=False, end="")
            return

        if (isinstance(operation, (PointerCast, Statement))):
            self.print(operation.statement.data)
            return

        if (isinstance(operation, StructDecl)):
            self.print("struct", indent=False, end=" ")
            self.print(operation.id.data)
            self.print("{")
            for field in operation.fields.data:
                self.print(field.data)
            self.print("};")
            self.print('')
            return

        self.print(f"// Operation {operation.name} not supported inprinter")