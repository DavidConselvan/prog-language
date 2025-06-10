// CMakeLists.txt
// ------------------------
cmake_minimum_required(VERSION 3.16)
project(domac LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)

# Find LLVM
find_package(LLVM REQUIRED CONFIG)
message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
include(AddLLVM)
include_directories(${LLVM_INCLUDE_DIRS})
add_definitions(${LLVM_DEFINITIONS})

# Flex & Bison integration
find_package(FLEX REQUIRED)
find_package(BISON REQUIRED)

FLEX_TARGET(Lexer src/dmc.l ${CMAKE_CURRENT_BINARY_DIR}/dmc_lexer.cpp)
BISON_TARGET(Parser src/dmc.y ${CMAKE_CURRENT_BINARY_DIR}/dmc_parser.cpp)
ADD_FLEX_BISON_DEPENDENCY(Lexer Parser)

add_executable(domac
    src/main.cpp
    src/AST.h src/AST.cpp
    src/CodeGen.h src/CodeGen.cpp
    src/runtime.h src/runtime.cpp
    ${BISON_Parser_OUTPUTS}
    ${FLEX_Lexer_OUTPUTS}
)

# Link LLVM libraries
llvm_map_components_to_libnames(LLVM_LIBS core orcjit native)
target_link_libraries(domac PRIVATE ${LLVM_LIBS})


// src/runtime.h
// ------------------------
#ifndef RUNTIME_H
#define RUNTIME_H
#include <cstdint>
extern "C" {
    void print_str(const char*);
    char* get_input();
    int64_t get_time();
    void wait_ms(int64_t);
    void save_file(const char*, const char*);
}
#endif

// src/runtime.cpp
// ------------------------
#include "runtime.h"
#include <iostream>
#include <string>
#include <ctime>
#include <thread>
#include <chrono>
#include <fstream>

extern "C" {
void print_str(const char* s) {
    std::cout << s;
}

char* get_input() {
    std::string line;
    std::getline(std::cin, line);
    char* cstr = (char*)malloc(line.size()+1);
    strcpy(cstr, line.c_str());
    return cstr;
}

int64_t get_time() {
    return std::time(nullptr) * 1000;
}

void wait_ms(int64_t ms) {
    std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

void save_file(const char* filename, const char* content) {
    std::ofstream out(filename);
    out << content;
    out.close();
}
}

// src/AST.h
// ------------------------
#pragma once
#include <memory>
#include <vector>
#include <string>
#include "llvm/IR/Value.h"

// Forward declare codegen context
typedef struct CodeGenContext CodeGenContext;

// Abstract base for expressions
struct ExprAST {
    virtual ~ExprAST() = default;
    virtual llvm::Value* codegen(CodeGenContext& ctx) = 0;
};

// Abstract base for statements
struct StmtAST {
    virtual ~StmtAST() = default;
    virtual void codegen(CodeGenContext& ctx) = 0;
};

// Examples of AST nodes
struct NumberExprAST : ExprAST {
    int64_t Val;
    NumberExprAST(int64_t V) : Val(V) {}
    llvm::Value* codegen(CodeGenContext& ctx) override;
};

struct VariableExprAST : ExprAST {
    std::string Name;
    VariableExprAST(const std::string& N) : Name(N) {}
    llvm::Value* codegen(CodeGenContext& ctx) override;
};

struct BinaryExprAST : ExprAST {
    char Op;
    std::unique_ptr<ExprAST> L, R;
    BinaryExprAST(char op, std::unique_ptr<ExprAST> LHS, std::unique_ptr<ExprAST> RHS)
        : Op(op), L(std::move(LHS)), R(std::move(RHS)) {}
    llvm::Value* codegen(CodeGenContext& ctx) override;
};

// Statement: print(expr)
struct PrintStmtAST : StmtAST {
    std::unique_ptr<ExprAST> Expr;
    PrintStmtAST(std::unique_ptr<ExprAST> E) : Expr(std::move(E)) {}
    void codegen(CodeGenContext& ctx) override;
};

// TODO: Add AST classes for InputStmt, IfStmt, WhileStmt, WaitStmt, SaveStmt, etc.

// Program container
struct ProgramAST {
    std::vector<std::unique_ptr<StmtAST>> Stmts;
    llvm::Value* codegen();
};

// src/AST.cpp
// ------------------------
#include "AST.h"
#include "CodeGen.h"

// Implement AST::codegen by delegating to CodeGen
llvm::Value* NumberExprAST::codegen(CodeGenContext& ctx) { return ctx.codegenNumber(Val); }
llvm::Value* VariableExprAST::codegen(CodeGenContext& ctx) { return ctx.codegenVariable(Name); }
llvm::Value* BinaryExprAST::codegen(CodeGenContext& ctx) { return ctx.codegenBinary(Op, *L, *R); }
void PrintStmtAST::codegen(CodeGenContext& ctx) { ctx.codegenPrint(*Expr); }
llvm::Value* ProgramAST::codegen() {
    CodeGenContext ctx;
    ctx.initializeModule();
    for (auto& stmt : Stmts) stmt->codegen(ctx);
    return ctx.runJIT();
}

// src/CodeGen.h
// ------------------------
#pragma once
#include "AST.h"
#include "llvm/IR/LLVMContext.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/ExecutionEngine/Orc/LLJIT.h"

struct CodeGenContext {
    llvm::LLVMContext TheContext;
    std::unique_ptr<llvm::Module> TheModule;
    std::unique_ptr<llvm::orc::LLJIT> JIT;
    llvm::IRBuilder<> Builder;
    // Symbol table for variable storage
    std::map<std::string, llvm::Value*> NamedValues;

    CodeGenContext(): Builder(TheContext) {}
    void initializeModule();
    llvm::Value* codegenNumber(int64_t Val);
    llvm::Value* codegenVariable(const std::string& Name);
    llvm::Value* codegenBinary(char Op, ExprAST& L, ExprAST& R);
    void codegenPrint(ExprAST& Expr);
    llvm::Value* runJIT();
};

// src/CodeGen.cpp
// ------------------------
#include "CodeGen.h"
#include "runtime.h"
#include <llvm/IR/Verifier.h>
#include <llvm/Support/Error.h>
#include <llvm/ExecutionEngine/Orc/ExecutionUtils.h>
#include <llvm/ExecutionEngine/Orc/ThreadSafeModule.h>

using namespace llvm;

void CodeGenContext::initializeModule() {
    TheModule = std::make_unique<Module>("domac", TheContext);
    // Declare external runtime functions
    auto &M = *TheModule;
    FunctionType *printTy = FunctionType::get(Type::getVoidTy(TheContext), {PointerType::getUnqual(Type::getInt8Ty(TheContext))}, false);
    M.getOrInsertFunction("print_str", printTy);
}

Value* CodeGenContext::codegenNumber(int64_t Val) {
    return ConstantInt::get(TheContext, APInt(64, Val));
}

Value* CodeGenContext::codegenVariable(const std::string& Name) {
    return NamedValues[Name];
}

Value* CodeGenContext::codegenBinary(char Op, ExprAST& LHS, ExprAST& RHS) {
    Value *L = LHS.codegen(*this);
    Value *R = RHS.codegen(*this);
    switch (Op) {
        case '+': return Builder.CreateAdd(L, R, "addtmp");
        case '-': return Builder.CreateSub(L, R, "subtmp");
        case '*': return Builder.CreateMul(L, R, "multmp");
        case '/': return Builder.CreateSDiv(L, R, "divtmp");
        default: return nullptr;
    }
}

void CodeGenContext::codegenPrint(ExprAST& Expr) {
    Value *Val = Expr.codegen(*this);
    // Convert int to string via sprintf (omitted for brevity) or assume Expr is string
    // Here, for simplicity, assume Expr.codegen returns i8* pointer
    Value *StrPtr = Val;
    Function *printF = TheModule->getFunction("print_str");
    Builder.CreateCall(printF, {StrPtr});
}

Value* CodeGenContext::runJIT() {
    auto TSM = ThreadSafeModule(std::move(TheModule), std::make_unique<LLVMContext>());
    auto J = cantFail(orc::LLJITBuilder().create());
    cantFail(J->addIRModule(std::move(TSM)));
    auto Sym = cantFail(J->lookup("main"));
    using MainFn = int (*)();
    auto *MainPtr = (MainFn)Sym.getAddress();
    return ConstantInt::get(TheContext, APInt(64, MainPtr()));
}

// src/main.cpp
// ------------------------
#include <iostream>
#include "AST.h"
#include <cstdio>

extern FILE* yyin;
ProgramAST* parseProgram();

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: domac <script.dmc>\n";
        return 1;
    }
    yyin = fopen(argv[1], "r");
    if (!yyin) { perror("fopen"); return 1; }
    ProgramAST* prog = parseProgram();  // From Bison-generated parser
    prog->codegen();
    return 0;
}
