#!/usr/bin/env python3

import argparse
import os
import sys
from io import StringIO

from devito.ir.ietxdsl import IET
from devito.xdslpasses.iet.parpragma import make_simd

from xdsl.parser import Parser
from xdsl.printer import Printer
from xdsl.ir import MLContext
from xdsl.dialects.builtin import Builtin, ModuleOp


from typing import Dict, Callable, List


class XdslOptMain:
    ctx: MLContext
    args: argparse.Namespace
    available_passes: Dict[str, Callable[[MLContext, ModuleOp], None]]
    pipeline: List[Callable[[ModuleOp], None]]

    passes_native = [make_simd]

    passes_integrated = [
        # TODO
    ]

    def __init__(self, args: argparse.Namespace):
        self.ctx = MLContext()
        self.args = args
        self.register_all_dialects()
        self.available_passes = self.get_passes_as_dict()

        if args.passes != 'all':
            pipeline = [
                str(item) for item in args.passes.split(',') if len(item) > 0
            ]
        else:
            if args.frontend == 'python-ast-to-tree':
                pipeline = XdslOptMain.get_passes_as_list(integrated=True)
            if args.frontend == 'native':
                pipeline = XdslOptMain.get_passes_as_list(native=True)

        for p in pipeline:
            if p not in self.available_passes:
                raise Exception(f"Unrecognized pass: {p}")

        self.pipeline = [
            lambda op, p=p: self.available_passes[p](self.ctx, op)
            for p in pipeline
        ]

    def register_all_dialects(self):
        """Register all dialects that can be used."""
        builtin = Builtin(self.ctx)  # noqa
        iet = IET(self.ctx)   # noqa

    @staticmethod
    def get_passes_as_dict(
    ) -> Dict[str, Callable[[MLContext, ModuleOp], None]]:
        """Add all passes that can be called by choco-opt in a dictionary."""

        pass_dictionary = {}

        passes = XdslOptMain.passes_native + XdslOptMain.passes_integrated

        for pass_function in passes:
            pass_dictionary[pass_function.__name__.replace(
                "_", "-")] = pass_function

        return pass_dictionary

    def get_passes_as_list(native=False, integrated=False) -> List[str]:
        """Add all passes that can be called by choco-opt in a dictionary."""

        pass_list = []

        assert not (native and integrated)

        if native:
            passes = XdslOptMain.passes_native
        elif integrated:
            passes = XdslOptMain.passes_integrated
        else:
            passes = XdslOptMain.passes_native + XdslOptMain.passes_integrated
        for pass_function in passes:
            pass_list.append(pass_function.__name__.replace("_", "-"))

        return pass_list

    def parse_frontend(self) -> ModuleOp:
        """Parse the input file."""
        if self.args.input_file is None:
            f = sys.stdin
            file_extension = '.xdsl'
        else:
            f = open(args.input_file, mode='r')
            _, file_extension = os.path.splitext(args.input_file)

        if file_extension == '.xdsl':
            input_str = f.read()
            parser = Parser(self.ctx, input_str)
            module = parser.parse_op()
            if not self.args.disable_verify:
                module.verify()
            if not (isinstance(module, ModuleOp)):
                raise Exception(
                    "Expected module or program as toplevel operation")
            return module

        raise Exception(f"Unrecognized file extension '{file_extension}'")

    def apply_passes(self, prog: ModuleOp):
        """Apply passes in order."""
        assert isinstance(prog, ModuleOp)
        if not self.args.disable_verify:
            prog.verify()
        for p in self.pipeline:
            p(prog)
            assert isinstance(prog, ModuleOp)
            if not self.args.disable_verify:
                prog.verify()

    def output_resulting_program(self, prog: ModuleOp) -> str:
        """Get the resulting program."""
        output = StringIO()
        if self.args.target == 'xdsl':
            printer = Printer(stream=output)
            printer.print_op(prog)
            return output.getvalue()
        if self.args.target == 'mlir':
            try:
                from xdsl.mlir_converter import MLIRConverter
            except ImportError as ex:
                raise Exception(
                    "Can only emit mlir if the mlir bindings are present"
                ) from ex
            converter = MLIRConverter(self.ctx)
            mlir_module = converter.convert_module(prog)
            print(mlir_module, file=output)
            return output.getvalue()
        raise Exception(f"Unknown target {self.args.target}")

    def print_to_output_stream(self, contents: str):
        """Print the contents in the expected stream."""
        if self.args.output_file is None:
            print(contents)
        else:
            output_stream = open(self.args.output_file, 'w')
            output_stream.write(contents)


passes = XdslOptMain.get_passes_as_list()
pass_names = ",".join(passes)

arg_parser = argparse.ArgumentParser(
    description='xDSL modular optimizer driver')
arg_parser.add_argument("input_file",
                        type=str,
                        nargs="?",
                        help="Path to input file")

arg_parser.add_argument(
    "-p",
    "--passes",
    required=False,
    help=f"Delimited list of passes. Available passes are: {pass_names} or 'all'",
    type=str,
    default="")
arg_parser.add_argument("-o",
                        "--output-file",
                        type=str,
                        required=False,
                        help="path to output file")

arg_parser.add_argument("-t",
                        "--target",
                        type=str,
                        choices=["xdsl", "mlir"],
                        default="xdsl")

arg_parser.add_argument("--disable-verify", default=False, action='store_true')


def __main__(args: argparse.Namespace):
    choco_main = XdslOptMain(args)

    try:
        module = choco_main.parse_frontend()
        choco_main.apply_passes(module)
    except SyntaxError as e:
        print(e.get_message())
        exit(0)

    contents = choco_main.output_resulting_program(module)
    choco_main.print_to_output_stream(contents)


if __name__ == "__main__":
    args = arg_parser.parse_args()
    __main__(args)
