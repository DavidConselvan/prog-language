Domac Language Specification
1. Motivation

Domac or DMC is a lightweight scripting language focused on simple task automation.
It combines Go-like clean syntax with essential commands for input, output, conditional flows, loops, timing, and file saving.
Domac empowers users to create quick and efficient automation scripts with minimal overhead.

2. Characteristics

  Variable declaration with var

  User input with input()

  Output printing with print()

  Conditional branching with if and optional else

  Loops with while

  Delay execution with wait(milliseconds)

  File writing with save(filename, content)

  Access to current system time with time()

  No semicolons at the end of statements

  No parentheses around if and while conditions

  Block structures defined with {}

3. Syntax Style

  Clean and simple, inspired by Go

  Case-sensitive

  Built-in commands and functions are in lowercase

  Each statement ends by a new line

4. EBNF
<program> ::= { <statement> } ;

<statement> ::= <variable-declaration>
              | <assignment>
              | <print-statement>
              | <input-statement>
              | <if-statement>
              | <while-statement>
              | <wait-statement>
              | <save-statement>
              | <blank-line> ;

<variable-declaration> ::= "var" <identifier> "=" <expression> ;

<assignment> ::= <identifier> "=" <expression> ;

<print-statement> ::= "print" "(" <expression> ")" ;

<input-statement> ::= <identifier> "=" "input" "(" ")" ;

<if-statement> ::= "if" <expression> <block> { "else" "if" <expression> <block> } [ "else" <block> ] ;

<while-statement> ::= "while" <expression> <block> ;

<wait-statement> ::= "wait" "(" <expression> ")" ;

<save-statement> ::= "save" "(" <expression> "," <expression> ")" ;

<block> ::= "{" { <statement> } "}" ;

<blank-line> ::= ;

<expression> ::= <comparison> ;

<comparison> ::= <addition> { ("==" | "!=" | "<" | ">" | "<=" | ">=") <addition> } ;

<addition> ::= <term> { ("+" | "-") <term> } ;

<term> ::= <factor> { ("*" | "/") <factor> } ;

<factor> ::= <number>
           | <string>
           | <identifier>
           | "time" "(" ")"
           | "(" <expression> ")" ;

<identifier> ::= <letter> { <letter> | <digit> | "_" } ;

<number> ::= <digit> { <digit> } ;

<string> ::= "\"" { <character> } "\"" ;

<letter> ::= "a" | "b" | ... | "z" | "A" | "B" | ... | "Z" ;

<digit> ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;

<character> ::= any ASCII character except `"` ;

Example Program
```
var x = 0
var name = input()

print("Welcome, " + name)

while x < 5 {
    print(x)
    wait(1000)
    x = x + 1
}

if x == 5 {
    save("log.txt", "Loop finished.")
    print("Program completed.")
}

```
