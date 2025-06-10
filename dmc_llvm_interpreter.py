#!/usr/bin/env python3
"""
DMC (Domac) Programming Language LLVM JIT Interpreter
Uses LLVM IR generation and JIT execution for direct interpretation
"""

import time
import re
import subprocess
import os
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
from ctypes import CFUNCTYPE, c_int

# LLVM Python bindings
try:
    from llvmlite import ir, binding
    from llvmlite.binding import *
    LLVM_AVAILABLE = True
except ImportError:
    print("llvmlite not available. Install with: pip install llvmlite")
    LLVM_AVAILABLE = False

def compile_parser():
    """Compile the flex-bison parser"""
    try:
        # Compile flex
        subprocess.run(['flex', 'dmc.l'], check=True)
        # Compile bison
        subprocess.run(['bison', '-d', 'dmc.y'], check=True)
        
        # Determine the flex library name based on platform
        import platform
        if platform.system() == 'Windows':
            # For MSYS2/MinGW64
            # Get flex installation path
            flex_path = subprocess.check_output(['which', 'flex']).decode().strip()
            print(f"Found flex at: {flex_path}")
            
            # Try to find libfl.a in common MSYS2 locations
            base_paths = [
                '/c/msys64',
                '/c/msys64/mingw64',
                '/usr',
                os.path.dirname(os.path.dirname(flex_path)),  # Try flex's parent directory
                '/mingw64',  # Additional MinGW paths
                '/mingw32'
            ]
            
            lib_paths = []
            for base in base_paths:
                lib_paths.extend([
                    os.path.join(base, 'lib', 'libfl.a'),
                    os.path.join(base, 'lib64', 'libfl.a'),
                    os.path.join(base, 'usr', 'lib', 'libfl.a'),
                    os.path.join(base, 'usr', 'lib64', 'libfl.a'),
                    os.path.join(base, 'local', 'lib', 'libfl.a'),
                    os.path.join(base, 'local', 'lib64', 'libfl.a')
                ])
            
            print("Searching for libfl.a in:")
            for path in lib_paths:
                # Convert backslashes to forward slashes for MSYS2
                path = path.replace('\\', '/')
                print(f"  - {path}")
                if os.path.exists(path):
                    print(f"Found libfl.a at: {path}")
                    # Compile with explicit path to libfl.a
                    subprocess.run(['gcc', '-o', 'dmc_parser', 'lex.yy.c', 'dmc.tab.c', path], check=True)
                    return True
            
            # If no libfl.a found, try to compile without it
            print("Warning: Could not find libfl.a. Trying without it...")
            try:
                # Try compiling with -lfl first
                subprocess.run(['gcc', '-o', 'dmc_parser', 'lex.yy.c', 'dmc.tab.c', '-lfl'], check=True)
                return True
            except subprocess.CalledProcessError:
                try:
                    # Then try without any flex library
                    subprocess.run(['gcc', '-o', 'dmc_parser', 'lex.yy.c', 'dmc.tab.c'], check=True)
                    return True
                except subprocess.CalledProcessError as e:
                    print(f"Error compiling without libfl.a: {e}")
                    print("\nPlease try installing flex with:")
                    print("  pacman -S flex")
                    print("\nIf that doesn't work, try:")
                    print("  pacman -S mingw-w64-x86_64-flex")
                    print("\nAfter installing, you may need to restart your terminal.")
                    return False
        else:
            # On Unix-like systems, use -lfl
            subprocess.run(['gcc', '-o', 'dmc_parser', 'lex.yy.c', 'dmc.tab.c', '-lfl'], check=True)
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"Error compiling parser: {e}")
        print("Make sure you have flex, bison, and gcc installed and in your PATH")
        print("If using MSYS2, try installing both flex packages:")
        print("  pacman -S flex")
        print("  pacman -S mingw-w64-x86_64-flex")
        print("\nAfter installing, you may need to restart your terminal.")
        return False
    except FileNotFoundError as e:
        print(f"Required tool not found: {e}")
        print("Make sure flex, bison, and gcc are installed and in your PATH")
        print("If using MSYS2, install them with:")
        print("  pacman -S flex bison mingw-w64-x86_64-gcc")
        print("  pacman -S mingw-w64-x86_64-flex")
        print("\nAfter installing, you may need to restart your terminal.")
        return False

def parse_with_flex_bison(source_code: str) -> List[dict]:
    """Parse source code using the flex-bison parser"""
    # Write source code to temporary file
    with open('temp.dmc', 'w') as f:
        f.write(source_code)
    
    try:
        # Run the parser
        result = subprocess.run(['./dmc_parser', 'temp.dmc'], 
                              capture_output=True, 
                              text=True, 
                              check=True)
        
        # Parse the output into AST nodes
        ast_nodes = []
        for line in result.stdout.splitlines():
            if line.strip():
                # Parse the line into an AST node
                # This is a simplified version - you'll need to adapt this to your parser's output format
                parts = line.split()
                if parts[0] == 'VAR':
                    ast_nodes.append({
                        'type': 'VarDeclaration',
                        'name': parts[1],
                        'value': parts[3]
                    })
                elif parts[0] == 'PRINT':
                    ast_nodes.append({
                        'type': 'PrintStatement',
                        'expression': parts[1]
                    })
                # Add more node types as needed
        
        return ast_nodes
    except subprocess.CalledProcessError as e:
        print(f"Error running parser: {e}")
        print(f"Parser output: {e.output}")
        return []
    finally:
        # Clean up temporary file
        if os.path.exists('temp.dmc'):
            os.remove('temp.dmc')

class ASTNode:
    pass

@dataclass
class Program(ASTNode):
    statements: List[ASTNode]

@dataclass 
class VarDeclaration(ASTNode):
    name: str
    value: ASTNode

@dataclass
class Assignment(ASTNode):
    name: str
    value: ASTNode

@dataclass
class PrintStatement(ASTNode):
    expression: ASTNode

@dataclass
class InputStatement(ASTNode):
    variable: str

@dataclass
class IfStatement(ASTNode):
    condition: ASTNode
    then_block: List[ASTNode]
    else_block: Optional[List[ASTNode]] = None

@dataclass
class WhileStatement(ASTNode):
    condition: ASTNode
    body: List[ASTNode]

@dataclass
class WaitStatement(ASTNode):
    milliseconds: ASTNode

@dataclass
class SaveStatement(ASTNode):
    filename: ASTNode
    content: ASTNode

@dataclass
class BinaryOp(ASTNode):
    left: ASTNode
    operator: str
    right: ASTNode

@dataclass
class UnaryOp(ASTNode):
    operator: str
    operand: ASTNode

@dataclass
class Literal(ASTNode):
    value: Union[int, float, str]

@dataclass
class Variable(ASTNode):
    name: str

@dataclass
class FunctionCall(ASTNode):
    name: str
    args: List[ASTNode] = None

def convert_to_ast(parser_output: List[dict]) -> Program:
    """Convert parser output to AST nodes"""
    statements = []
    for node in parser_output:
        if node['type'] == 'VarDeclaration':
            statements.append(VarDeclaration(
                name=node['name'],
                value=parse_expression(node['value'])
            ))
        elif node['type'] == 'PrintStatement':
            statements.append(PrintStatement(
                expression=parse_expression(node['expression'])
            ))
        # Add more node types as needed
    return Program(statements)

def parse_expression(expr: str) -> ASTNode:
    """Parse an expression string into an AST node"""
    # This is a simplified version - you'll need to adapt this to your parser's output format
    if expr.isdigit():
        return Literal(int(expr))
    elif expr.startswith('"') and expr.endswith('"'):
        return Literal(expr[1:-1])
    else:
        return Variable(expr)

class DMCLLVMGenerator:
    """Generates LLVM IR from DMC AST and executes with JIT"""
    
    def __init__(self):
        if not LLVM_AVAILABLE:
            raise RuntimeError("LLVM not available")
        
        # Initialize LLVM
        binding.initialize()
        binding.initialize_native_target()
        binding.initialize_native_asmprinter()
        
        # Create module and builder
        self.module = ir.Module(name="dmc_module")
        self.builder = None
        self.variables = {}
        
        # Create runtime functions
        self.create_runtime_functions()
        
        # Create main function
        self.create_main_function()
    
    def create_runtime_functions(self):
        """Create external runtime functions for I/O operations"""
        
        # printf function
        printf_ty = ir.FunctionType(ir.IntType(32), [ir.IntType(8).as_pointer()], var_arg=True)
        self.printf_func = ir.Function(self.module, printf_ty, name="printf")
        
        # scanf function
        scanf_ty = ir.FunctionType(ir.IntType(32), [ir.IntType(8).as_pointer()], var_arg=True)
        self.scanf_func = ir.Function(self.module, scanf_ty, name="scanf")
        
        # malloc function
        malloc_ty = ir.FunctionType(ir.IntType(8).as_pointer(), [ir.IntType(64)])
        self.malloc_func = ir.Function(self.module, malloc_ty, name="malloc")
        
        # sleep function (for wait)
        sleep_ty = ir.FunctionType(ir.VoidType(), [ir.IntType(32)])
        self.sleep_func = ir.Function(self.module, sleep_ty, name="sleep")
        
        # time function
        time_ty = ir.FunctionType(ir.DoubleType(), [])
        self.time_func = ir.Function(self.module, time_ty, name="time")
        
        # fopen function
        fopen_ty = ir.FunctionType(ir.IntType(8).as_pointer(), [ir.IntType(8).as_pointer(), ir.IntType(8).as_pointer()])
        self.fopen_func = ir.Function(self.module, fopen_ty, name="fopen")
        
        # fprintf function
        fprintf_ty = ir.FunctionType(ir.IntType(32), [ir.IntType(8).as_pointer(), ir.IntType(8).as_pointer()], var_arg=True)
        self.fprintf_func = ir.Function(self.module, fprintf_ty, name="fprintf")
        
        # fclose function
        fclose_ty = ir.FunctionType(ir.IntType(32), [ir.IntType(8).as_pointer()])
        self.fclose_func = ir.Function(self.module, fclose_ty, name="fclose")
    
    def create_main_function(self):
        """Create the main function where DMC code will be executed"""
        main_ty = ir.FunctionType(ir.IntType(32), [])
        self.main_func = ir.Function(self.module, main_ty, name="main")
        self.entry_block = self.main_func.append_basic_block(name="entry")
        self.builder = ir.IRBuilder(self.entry_block)
    
    def generate(self, ast: Program):
        """Generate LLVM IR from AST"""
        
        # Generate code for each statement
        for stmt in ast.statements:
            self.visit(stmt)
        
        # Return 0 from main
        self.builder.ret(ir.Constant(ir.IntType(32), 0))
        
        return self.module
    
    def visit(self, node: ASTNode):
        """Visit AST node and generate appropriate LLVM IR"""
        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)
    
    def generic_visit(self, node: ASTNode):
        raise NotImplementedError(f"No visitor for {type(node).__name__}")
    
    def visit_VarDeclaration(self, node: VarDeclaration):
        """Generate IR for variable declarations"""
        # Generate code for the initial value first to determine type
        value = self.visit(node.value)
        
        # Get string pointer type for comparison
        string_type = ir.IntType(8).as_pointer()
        
        # Determine variable type based on value type
        if value.type == string_type:  # String type
            var_type = string_type
        else:  # Numeric type
            var_type = ir.DoubleType()
        
        # Allocate space for the variable
        var_ptr = self.builder.alloca(var_type, name=node.name)
        
        # Store the value
        self.builder.store(value, var_ptr)
        self.variables[node.name] = var_ptr
        return var_ptr
    
    def visit_Assignment(self, node: Assignment):
        """Generate IR for assignments"""
        value = self.visit(node.value)
        
        # Get string pointer type for comparison
        string_type = ir.IntType(8).as_pointer()
        
        if node.name not in self.variables:
            # Auto-declare variable if not exists
            if value.type == string_type:  # String type
                var_type = string_type
            else:  # Numeric type
                var_type = ir.DoubleType()
            var_ptr = self.builder.alloca(var_type, name=node.name)
            self.variables[node.name] = var_ptr
        
        # Convert to double if needed
        if isinstance(value.type, ir.IntType) and value.type != string_type:
            value = self.builder.sitofp(value, ir.DoubleType())
        
        self.builder.store(value, self.variables[node.name])
        return value
    
    def visit_PrintStatement(self, node: PrintStatement):
        """Generate IR for print statements"""
        value = self.visit(node.expression)
        
        # Get string pointer type for comparison
        string_type = ir.IntType(8).as_pointer()
        
        # Create format string for printf based on value type
        if isinstance(value.type, ir.DoubleType):
            fmt_str = "%.2f\n"
        elif value.type == string_type:
            fmt_str = "%s\n"
        else:
            fmt_str = "%d\n"
        
        # Create global string constant
        fmt_const = ir.Constant(ir.ArrayType(ir.IntType(8), len(fmt_str) + 1), 
                               bytearray(fmt_str.encode('utf-8')) + bytearray([0]))
        fmt_global = ir.GlobalVariable(self.module, fmt_const.type, name=f"fmt_{len(self.module.globals)}")
        fmt_global.initializer = fmt_const
        fmt_global.global_constant = True
        
        # Get pointer to format string
        fmt_ptr = self.builder.gep(fmt_global, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
        
        # Call printf
        self.builder.call(self.printf_func, [fmt_ptr, value])
        return value
    
    def visit_Variable(self, node: Variable):
        """Generate IR for variable references"""
        if node.name not in self.variables:
            raise RuntimeError(f"Undefined variable: {node.name}")
        
        return self.builder.load(self.variables[node.name])
    
    def visit_Literal(self, node: Literal):
        """Generate IR for literals"""
        if isinstance(node.value, (int, float)):
            return ir.Constant(ir.DoubleType(), float(node.value))
        elif isinstance(node.value, str):
            # Create string constant
            str_const = ir.Constant(ir.ArrayType(ir.IntType(8), len(node.value) + 1), 
                                  bytearray(node.value.encode('utf-8')) + bytearray([0]))
            str_global = ir.GlobalVariable(self.module, str_const.type, name=f"str_{len(self.module.globals)}")
            str_global.initializer = str_const
            str_global.global_constant = True
            return self.builder.gep(str_global, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
        else:
            raise RuntimeError(f"Unknown literal type: {type(node.value)}")
    
    def visit_BinaryOp(self, node: BinaryOp):
        """Generate IR for binary operations"""
        left = self.visit(node.left)
        right = self.visit(node.right)
        
        # Get string pointer type for comparison
        string_type = ir.IntType(8).as_pointer()
        
        # Handle string concatenation
        if node.operator == '+' and left.type == string_type and right.type == string_type:
            # For now, just return the left string - proper string concatenation needs more work
            return left
        
        # Convert to double if needed
        if isinstance(left.type, ir.IntType) and left.type != string_type:
            left = self.builder.sitofp(left, ir.DoubleType())
        if isinstance(right.type, ir.IntType) and right.type != string_type:
            right = self.builder.sitofp(right, ir.DoubleType())
        
        if node.operator == '+':
            return self.builder.fadd(left, right)
        elif node.operator == '-':
            return self.builder.fsub(left, right)
        elif node.operator == '*':
            return self.builder.fmul(left, right)
        elif node.operator == '/':
            return self.builder.fdiv(left, right)
        elif node.operator == '==':
            cmp_result = self.builder.fcmp_ordered('==', left, right)
            return self.builder.uitofp(cmp_result, ir.DoubleType())
        elif node.operator == '!=':
            cmp_result = self.builder.fcmp_ordered('!=', left, right)
            return self.builder.uitofp(cmp_result, ir.DoubleType())
        elif node.operator == '<':
            cmp_result = self.builder.fcmp_ordered('<', left, right)
            return self.builder.uitofp(cmp_result, ir.DoubleType())
        elif node.operator == '>':
            cmp_result = self.builder.fcmp_ordered('>', left, right)
            return self.builder.uitofp(cmp_result, ir.DoubleType())
        elif node.operator == '<=':
            cmp_result = self.builder.fcmp_ordered('<=', left, right)
            return self.builder.uitofp(cmp_result, ir.DoubleType())
        elif node.operator == '>=':
            cmp_result = self.builder.fcmp_ordered('>=', left, right)
            return self.builder.uitofp(cmp_result, ir.DoubleType())
        else:
            raise RuntimeError(f"Unknown binary operator: {node.operator}")
    
    def visit_WhileStatement(self, node: WhileStatement):
        """Generate IR for while loops"""
        # Create basic blocks
        loop_cond = self.main_func.append_basic_block(name="loop_cond")
        loop_body = self.main_func.append_basic_block(name="loop_body")
        loop_end = self.main_func.append_basic_block(name="loop_end")
        
        # Jump to condition check
        self.builder.branch(loop_cond)
        
        # Generate condition check
        self.builder.position_at_end(loop_cond)
        condition = self.visit(node.condition)
        
        # Convert condition to i1
        zero = ir.Constant(ir.DoubleType(), 0.0)
        cond_bool = self.builder.fcmp_ordered('!=', condition, zero)
        
        # Conditional branch
        self.builder.cbranch(cond_bool, loop_body, loop_end)
        
        # Generate loop body
        self.builder.position_at_end(loop_body)
        for stmt in node.body:
            self.visit(stmt)
        self.builder.branch(loop_cond)
        
        # Continue after loop
        self.builder.position_at_end(loop_end)
    
    def visit_IfStatement(self, node: IfStatement):
        """Generate IR for if statements"""
        # Create basic blocks
        then_block = self.main_func.append_basic_block(name="if_then")
        else_block = self.main_func.append_basic_block(name="if_else") if node.else_block else None
        merge_block = self.main_func.append_basic_block(name="if_merge")
        
        # Generate condition
        condition = self.visit(node.condition)
        
        # Convert condition to i1
        zero = ir.Constant(ir.DoubleType(), 0.0)
        cond_bool = self.builder.fcmp_ordered('!=', condition, zero)
        
        # Conditional branch
        if else_block:
            self.builder.cbranch(cond_bool, then_block, else_block)
        else:
            self.builder.cbranch(cond_bool, then_block, merge_block)
        
        # Generate then block
        self.builder.position_at_end(then_block)
        for stmt in node.then_block:
            self.visit(stmt)
        self.builder.branch(merge_block)
        
        # Generate else block if present
        if else_block and node.else_block:
            self.builder.position_at_end(else_block)
            for stmt in node.else_block:
                self.visit(stmt)
            self.builder.branch(merge_block)
        
        # Continue after if
        self.builder.position_at_end(merge_block)

    def visit_InputStatement(self, node: InputStatement):
        """Generate IR for input statements"""
        # Create format string for scanf
        fmt_str = "%s"
        fmt_const = ir.Constant(ir.ArrayType(ir.IntType(8), len(fmt_str) + 1), 
                               bytearray(fmt_str.encode('utf-8')) + bytearray([0]))
        fmt_global = ir.GlobalVariable(self.module, fmt_const.type, name=f"fmt_input_{len(self.module.globals)}")
        fmt_global.initializer = fmt_const
        fmt_global.global_constant = True
        fmt_ptr = self.builder.gep(fmt_global, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
        
        # Allocate buffer for input
        buffer_size = 256
        buffer = self.builder.call(self.malloc_func, [ir.Constant(ir.IntType(64), buffer_size)])
        
        # Call scanf
        self.builder.call(self.scanf_func, [fmt_ptr, buffer])
        
        # Store in variable
        if node.variable not in self.variables:
            var_type = ir.IntType(8).as_pointer()
            var_ptr = self.builder.alloca(var_type, name=node.variable)
            self.variables[node.variable] = var_ptr
        
        self.builder.store(buffer, self.variables[node.variable])
        return buffer  # Return the buffer pointer

    def visit_FunctionCall(self, node: FunctionCall):
        """Generate IR for function calls"""
        if node.name == 'time':
            return self.builder.call(self.time_func, [])
        elif node.name == 'input':
            # Create format string for scanf
            fmt_str = "%s"
            fmt_const = ir.Constant(ir.ArrayType(ir.IntType(8), len(fmt_str) + 1), 
                                  bytearray(fmt_str.encode('utf-8')) + bytearray([0]))
            fmt_global = ir.GlobalVariable(self.module, fmt_const.type, name=f"fmt_input_{len(self.module.globals)}")
            fmt_global.initializer = fmt_const
            fmt_global.global_constant = True
            fmt_ptr = self.builder.gep(fmt_global, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
            
            # Allocate buffer for input
            buffer_size = 256
            buffer = self.builder.call(self.malloc_func, [ir.Constant(ir.IntType(64), buffer_size)])
            
            # Call scanf
            self.builder.call(self.scanf_func, [fmt_ptr, buffer])
            return buffer
        else:
            raise RuntimeError(f"Unknown function: {node.name}")

    def visit_WaitStatement(self, node: WaitStatement):
        """Generate IR for wait statements"""
        milliseconds = self.visit(node.milliseconds)
        
        # Convert to integer if needed
        if isinstance(milliseconds.type, ir.DoubleType):
            milliseconds = self.builder.fptosi(milliseconds, ir.IntType(32))
        
        self.builder.call(self.sleep_func, [milliseconds])
        return milliseconds  # Return the wait duration

    def visit_SaveStatement(self, node: SaveStatement):
        """Generate IR for save statements"""
        filename = self.visit(node.filename)
        content = self.visit(node.content)
        
        # Create format string for fopen
        mode_str = "w"
        mode_const = ir.Constant(ir.ArrayType(ir.IntType(8), len(mode_str) + 1), 
                               bytearray(mode_str.encode('utf-8')) + bytearray([0]))
        mode_global = ir.GlobalVariable(self.module, mode_const.type, name=f"mode_{len(self.module.globals)}")
        mode_global.initializer = mode_const
        mode_global.global_constant = True
        mode_ptr = self.builder.gep(mode_global, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
        
        # Open file
        file_ptr = self.builder.call(self.fopen_func, [filename, mode_ptr])
        
        # Create format string for fprintf
        fmt_str = "%s"
        fmt_const = ir.Constant(ir.ArrayType(ir.IntType(8), len(fmt_str) + 1), 
                               bytearray(fmt_str.encode('utf-8')) + bytearray([0]))
        fmt_global = ir.GlobalVariable(self.module, fmt_const.type, name=f"fmt_save_{len(self.module.globals)}")
        fmt_global.initializer = fmt_const
        fmt_global.global_constant = True
        fmt_ptr = self.builder.gep(fmt_global, [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
        
        # Write content
        self.builder.call(self.fprintf_func, [file_ptr, fmt_ptr, content])
        
        # Close file
        self.builder.call(self.fclose_func, [file_ptr])
        return file_ptr  # Return the file pointer

def run_dmc_with_llvm(source_code: str):
    """Run DMC program using LLVM JIT compilation"""
    if not LLVM_AVAILABLE:
        print("LLVM not available. Please install llvmlite.")
        return
    
    try:
        # Parse source using flex-bison
        parser_output = parse_with_flex_bison(source_code)
        if not parser_output:
            print("Parser failed to generate AST")
            return
        
        # Convert parser output to AST
        ast = convert_to_ast(parser_output)
        
        # Generate LLVM IR
        llvm_gen = DMCLLVMGenerator()
        module = llvm_gen.generate(ast)
        
        print("Generated LLVM IR:")
        print("=" * 50)
        print(str(module))
        print("=" * 50)
        
        # Create execution engine
        llvm_module = binding.parse_assembly(str(module))
        target = binding.Target.from_default_triple()
        target_machine = target.create_target_machine()
        
        # Create JIT execution engine
        with binding.create_mcjit_compiler(llvm_module, target_machine) as ee:
            ee.finalize_object()
            
            # Get function pointer and execute
            func_ptr = ee.get_function_address("main")
            
            print("\nExecuting with LLVM JIT:")
            print("=" * 30)
            
            # Create a C function type for main
            main_type = CFUNCTYPE(c_int)
            main_func = main_type(func_ptr)
            
            # Execute the function
            result = main_func()
            print(f"\nProgram completed with exit code: {result}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

# Example usage
if __name__ == "__main__":
    # Compile the parser first
    if not compile_parser():
        print("Failed to compile parser. Exiting.")
        exit(1)
    
    # Read example program
    with open('exemplo.dmc', 'r') as f:
        test_program = f.read()
    
    print("DMC LLVM JIT Interpreter")
    print("=" * 50)
    
    if LLVM_AVAILABLE:
        run_dmc_with_llvm(test_program)
    else:
        print("Install llvmlite with: pip install llvmlite")
        print("Then run this script to see LLVM IR generation!")