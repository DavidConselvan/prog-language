#!/usr/bin/env python3
"""
DMC (Domac) Programming Language LLVM JIT Interpreter
Uses LLVM IR generation and JIT execution for direct interpretation
"""

import time
import re
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

# LLVM Python bindings
try:
    from llvmlite import ir, binding
    from llvmlite.binding import *
    LLVM_AVAILABLE = True
except ImportError:
    print("llvmlite not available. Install with: pip install llvmlite")
    LLVM_AVAILABLE = False

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

class DMCTokenizer:
    """Simple tokenizer for DMC programs"""
    
    TOKEN_PATTERNS = [
        ('NUMBER', r'\d+(\.\d+)?'),
        ('STRING', r'"[^"]*"'),
        ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z0-9_]*'),
        ('EQ', r'=='),
        ('NE', r'!='),
        ('LE', r'<='),
        ('GE', r'>='),
        ('ASSIGN', r'='),
        ('LT', r'<'),
        ('GT', r'>'),
        ('PLUS', r'\+'),
        ('MINUS', r'-'),
        ('MULT', r'\*'),
        ('DIV', r'/'),
        ('LPAREN', r'\('),
        ('RPAREN', r'\)'),
        ('LBRACE', r'\{'),
        ('RBRACE', r'\}'),
        ('COMMA', r','),
        ('WHITESPACE', r'\s+'),
        ('COMMENT', r'#.*'),
        ('NEWLINE', r'\n'),
    ]
    
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.tokens = []
        self._tokenize()
    
    def _tokenize(self):
        while self.pos < len(self.text):
            matched = False
            for token_type, pattern in self.TOKEN_PATTERNS:
                regex = re.compile(pattern)
                match = regex.match(self.text, self.pos)
                if match:
                    value = match.group(0)
                    if token_type not in ['WHITESPACE', 'COMMENT']:
                        self.tokens.append((token_type, value))
                    self.pos = match.end()
                    matched = True
                    break
            if not matched:
                raise SyntaxError(f"Unexpected character at position {self.pos}: {self.text[self.pos]}")

class DMCParser:
    """Parser that builds an AST from DMC tokens"""
    
    def __init__(self, tokens: List[tuple]):
        self.tokens = tokens
        self.pos = 0
    
    def current_token(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None
    
    def advance(self):
        self.pos += 1
    
    def expect(self, token_type: str):
        token = self.current_token()
        if not token or token[0] != token_type:
            raise SyntaxError(f"Expected {token_type}, got {token}")
        self.advance()
        return token[1]
    
    def parse(self) -> Program:
        statements = []
        while self.pos < len(self.tokens):
            if self.current_token()[0] == 'NEWLINE':
                self.advance()
                continue
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        return Program(statements)
    
    def parse_statement(self) -> Optional[ASTNode]:
        token = self.current_token()
        if not token:
            return None
            
        if token[1] == 'var':
            return self.parse_var_declaration()
        elif token[1] == 'print':
            return self.parse_print()
        elif token[1] == 'if':
            return self.parse_if()
        elif token[1] == 'while':
            return self.parse_while()
        elif token[1] == 'wait':
            return self.parse_wait()
        elif token[1] == 'save':
            return self.parse_save()
        elif token[0] == 'IDENTIFIER':
            return self.parse_assignment()
        else:
            self.advance()
            return None
    
    def parse_var_declaration(self) -> VarDeclaration:
        self.expect('IDENTIFIER')  # var
        name = self.expect('IDENTIFIER')
        self.expect('ASSIGN')
        value = self.parse_expression()
        return VarDeclaration(name, value)
    
    def parse_assignment(self) -> Assignment:
        name = self.expect('IDENTIFIER')
        if self.current_token() and self.current_token()[1] == '=':
            if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1][1] == 'input':
                self.advance()  # skip =
                self.advance()  # skip input
                self.expect('LPAREN')
                self.expect('RPAREN')
                return InputStatement(name)
            else:
                self.expect('ASSIGN')
                value = self.parse_expression()
                return Assignment(name, value)
        return Variable(name)
    
    def parse_print(self) -> PrintStatement:
        self.expect('IDENTIFIER')  # print
        self.expect('LPAREN')
        expr = self.parse_expression()
        self.expect('RPAREN')
        return PrintStatement(expr)
    
    def parse_if(self) -> IfStatement:
        self.expect('IDENTIFIER')  # if
        condition = self.parse_expression()
        then_block = self.parse_block()
        
        else_block = None
        if self.current_token() and self.current_token()[1] == 'else':
            self.advance()
            else_block = self.parse_block()
        
        return IfStatement(condition, then_block, else_block)
    
    def parse_while(self) -> WhileStatement:
        self.expect('IDENTIFIER')  # while
        condition = self.parse_expression()
        body = self.parse_block()
        return WhileStatement(condition, body)
    
    def parse_wait(self) -> WaitStatement:
        self.expect('IDENTIFIER')  # wait
        self.expect('LPAREN')
        milliseconds = self.parse_expression()
        self.expect('RPAREN')
        return WaitStatement(milliseconds)
    
    def parse_save(self) -> SaveStatement:
        self.expect('IDENTIFIER')  # save
        self.expect('LPAREN')
        filename = self.parse_expression()
        self.expect('COMMA')
        content = self.parse_expression()
        self.expect('RPAREN')
        return SaveStatement(filename, content)
    
    def parse_block(self) -> List[ASTNode]:
        self.expect('LBRACE')
        statements = []
        while self.current_token() and self.current_token()[0] != 'RBRACE':
            if self.current_token()[0] == 'NEWLINE':
                self.advance()
                continue
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        self.expect('RBRACE')
        return statements
    
    def parse_expression(self) -> ASTNode:
        return self.parse_comparison()
    
    def parse_comparison(self) -> ASTNode:
        left = self.parse_addition()
        
        while self.current_token() and self.current_token()[0] in ['EQ', 'NE', 'LT', 'GT', 'LE', 'GE']:
            op = self.current_token()[1]
            self.advance()
            right = self.parse_addition()
            left = BinaryOp(left, op, right)
        
        return left
    
    def parse_addition(self) -> ASTNode:
        left = self.parse_term()
        
        while self.current_token() and self.current_token()[0] in ['PLUS', 'MINUS']:
            op = self.current_token()[1]
            self.advance()
            right = self.parse_term()
            left = BinaryOp(left, op, right)
        
        return left
    
    def parse_term(self) -> ASTNode:
        left = self.parse_factor()
        
        while self.current_token() and self.current_token()[0] in ['MULT', 'DIV']:
            op = self.current_token()[1]
            self.advance()
            right = self.parse_factor()
            left = BinaryOp(left, op, right)
        
        return left
    
    def parse_factor(self) -> ASTNode:
        token = self.current_token()
        if not token:
            raise SyntaxError("Unexpected end of input")
            
        if token[0] == 'NUMBER':
            value = float(token[1]) if '.' in token[1] else int(token[1])
            self.advance()
            return Literal(value)
        elif token[0] == 'STRING':
            value = token[1][1:-1]  # Remove quotes
            self.advance()
            return Literal(value)
        elif token[0] == 'IDENTIFIER':
            if token[1] == 'time':
                self.advance()
                self.expect('LPAREN')
                self.expect('RPAREN')
                return FunctionCall('time')
            else:
                name = token[1]
                self.advance()
                return Variable(name)
        elif token[0] == 'LPAREN':
            self.advance()
            expr = self.parse_expression()
            self.expect('RPAREN')
            return expr
        else:
            raise SyntaxError(f"Unexpected token: {token}")

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
        # Allocate space for the variable
        var_type = ir.DoubleType()  # Use double for all values for simplicity
        var_ptr = self.builder.alloca(var_type, name=node.name)
        
        # Generate code for the initial value
        value = self.visit(node.value)
        
        # Convert to double if needed
        if isinstance(value.type, ir.IntegerType):
            value = self.builder.sitofp(value, ir.DoubleType())
        
        # Store the value
        self.builder.store(value, var_ptr)
        self.variables[node.name] = var_ptr
    
    def visit_Assignment(self, node: Assignment):
        """Generate IR for assignments"""
        if node.name not in self.variables:
            # Auto-declare variable if not exists
            var_type = ir.DoubleType()
            var_ptr = self.builder.alloca(var_type, name=node.name)
            self.variables[node.name] = var_ptr
        
        value = self.visit(node.value)
        
        # Convert to double if needed
        if isinstance(value.type, ir.IntegerType):
            value = self.builder.sitofp(value, ir.DoubleType())
        
        self.builder.store(value, self.variables[node.name])
    
    def visit_PrintStatement(self, node: PrintStatement):
        """Generate IR for print statements"""
        value = self.visit(node.expression)
        
        # Create format string for printf
        if isinstance(value.type, ir.DoubleType):
            fmt_str = "%.2f\n"
        else:
            fmt_str = "%s\n"
        
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
            # For now, just return a placeholder - string handling needs more work
            return ir.Constant(ir.DoubleType(), 0.0)
        else:
            raise RuntimeError(f"Unknown literal type: {type(node.value)}")
    
    def visit_BinaryOp(self, node: BinaryOp):
        """Generate IR for binary operations"""
        left = self.visit(node.left)
        right = self.visit(node.right)
        
        # Convert to double if needed
        if isinstance(left.type, ir.IntegerType):
            left = self.builder.sitofp(left, ir.DoubleType())
        if isinstance(right.type, ir.IntegerType):
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

def run_dmc_with_llvm(source_code: str):
    """Run DMC program using LLVM JIT compilation"""
    if not LLVM_AVAILABLE:
        print("LLVM not available. Please install llvmlite.")
        return
    
    try:
        # Parse source to AST
        tokenizer = DMCTokenizer(source_code)
        parser = DMCParser(tokenizer.tokens)
        ast = parser.parse()
        
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
            
            # This is a simplified example - full execution would need more setup
            print("LLVM IR generated successfully!")
            print("Note: Full JIT execution requires linking with C runtime")
            print("The IR shows the compiled DMC program structure")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

# Example usage
if __name__ == "__main__":
    # Simple test program
    test_program = '''
var x = 5
var y = 10
var z = x + y
print(z)
while x < 10 {
    x = x + 1
    print(x)
}
'''
    
    print("DMC LLVM JIT Interpreter")
    print("=" * 50)
    
    if LLVM_AVAILABLE:
        run_dmc_with_llvm(test_program)
    else:
        print("Install llvmlite with: pip install llvmlite")
        print("Then run this script to see LLVM IR generation!")