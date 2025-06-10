# DMC Language — Build & Run

## Pré-requisitos

* LLVM toolchain (incluindo `clang`, `llvm-as`)
* Flex e Bison
* Make (opcional, mas recomendado)

## Passos de Build

1. **Compilar o suporte C**

   ```bash
   clang -c support.c -o support.o
   ```

2. **Gerar o parser**

   Se estiver usando Makefile:

   ```bash
   make
   ```

   Sem Makefile:

   ```bash
   bison -d dmc.y       # gera dmc.tab.c e dmc.tab.h
   flex  dmc.l          # gera lex.yy.c
   gcc   -o dmc_parser lex.yy.c dmc.tab.c -lfl  # ou clang/gcc
   ```

3. **Parse → IR**

   ```bash
   ./dmc_parser exemplo.dmc
   ```

   Isso produz o arquivo `program.ll`.

4. **Montar bitcode**

   ```bash
   llvm-as program.ll -o program.bc
   ```

5. **Linkar e gerar executável**

   ```bash
   clang program.bc support.o -o programa
   ```

## Executar

```bash
./programa exemplo.dmc
```

> **Dica**: use um Makefile com alvos para cada etapa (`support.o`, `parser`, `program.ll`, `program.bc`, `programa`) para automatizar o build e simplificar o fluxo de desenvolvimento.
