%{
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>   // for usleep
#include <time.h>     // for time

void yyerror(char *);
int yylex(void);
extern int line_num;
extern char* yytext;
extern FILE *yyin;

void *global_ast;

// Function to print AST
void print_ast(void *node, int level);

void codegen(FILE *out, void *node);

static int tmp_counter = 0;  // Global counter for LLVM SSA registers - começa em 0

int codegen_expr(FILE *out, void *node);

typedef struct {
    int is_string;  // 0 = int, 1 = string
    union {
        int int_value;
        char *str_value;
    };
} Value;

typedef struct {
    char name[100];
    Value value;
} Variable;

Variable vars[100];
int var_count = 0;

static int string_literal_counter = 0;
static char* string_literals[1000];  // Array to store string literals
static int string_literal_count = 0;  // Count of stored string literals

char *escape_string_for_llvm(const char *input) {
    static char buffer[4096];
    char *p = buffer;
    const unsigned char *u = (const unsigned char*)input;

    while (*u) {
        if (*u >= 32 && *u < 127 && *u != '\\' && *u != '"') {
            *p++ = *u;
        } else {
            sprintf(p, "\\%02X", *u);
            p += 4;
        }
        u++;
    }
    *p = '\0';
    return buffer;
}

FILE *header_out;  // usado em codegen_string_literal   
const char* codegen_string_literal(FILE *header_out, const char *str) {
    static char name[100];
    sprintf(name, "str_%d", string_literal_counter++);
    
    // Store the string literal for later emission
    string_literals[string_literal_count++] = strdup(str);
    
    return name;
}



void set_variable(const char *name, Value value) {
    for (int i = 0; i < var_count; i++) {
        if (strcmp(vars[i].name, name) == 0) {
            vars[i].value = value;
            return;
        }
    }
    strcpy(vars[var_count].name, name);
    vars[var_count].value = value;
    var_count++;
}

Value get_variable(const char *name) {
    for (int i = 0; i < var_count; i++) {
        if (strcmp(vars[i].name, name) == 0) {
            return vars[i].value;
        }
    }
    printf("Undefined variable: %s\n", name);
    exit(1);
}

%}

%union {
    int num;
    char* str;
    char* id;
    void* node;
}

%token <num> NUMBER
%token <str> STRING
%token <id> IDENTIFIER
%token VAR IF ELSE WHILE PRINT INPUT WAIT SAVE TIME
%token EQ NE LE GE LT GT ASSIGN PLUS MINUS MULT DIV
%token LBRACE RBRACE LPAREN RPAREN COMMA NEWLINE

%nonassoc LOWER_THAN_ELSE
%nonassoc ELSE

%type <node> program statements statement
%type <node> variable_declaration assignment print_statement input_statement
%type <node> if_statement while_statement wait_statement save_statement
%type <node> block expression comparison addition term factor
%type <node> else_clause_opt


%%

program: statements { 
    printf("\nAbstract Syntax Tree:\n");
    print_ast($1, 0);
    global_ast = $1;
    $$ = $1;
}
    ;

statements
    : statement {
        if ($1 != NULL) {
            printf("Statement node type: %s\n", (char*)((void**)($1))[0]);
            $$ = $1;
        } else {
            $$ = NULL;
        }
    }
    | statements statement {
    if ($2 == NULL) {
        $$ = $1;
    } else if ($1 == NULL) {
        printf("Statement node type: %s\n", (char*)((void**)($2))[0]);
        $$ = $2;
    } else {
        void** node = malloc(4 * sizeof(void*));  // not 3 → add space for NULL
        node[0] = strdup("statements");
        node[1] = $1;
        node[2] = $2;
        node[3] = NULL;  // <== THIS FIXES THE SEGFAULT
        printf("Statements node type: %s\n", (char*)((void**)($2))[0]);
        $$ = node;
    }
}

;

statement: variable_declaration { $$ = $1; }
        | assignment { $$ = $1; }
        | print_statement { $$ = $1; }
        | if_statement { $$ = $1; }
        | while_statement { $$ = $1; }
        | input_statement { $$ = $1; }
        | wait_statement { $$ = $1; }
        | save_statement { $$ = $1; }
        | NEWLINE { $$ = NULL; }
    ;

variable_declaration: VAR IDENTIFIER ASSIGN expression NEWLINE {
    void** node = malloc(4 * sizeof(void*));
    node[0] = strdup("var_decl");
    node[1] = strdup($2);
    node[2] = $4;
    node[3] = NULL;
    $$ = node;
}
    ;

assignment: IDENTIFIER ASSIGN expression NEWLINE {
    void** node = malloc(4 * sizeof(void*));
    node[0] = strdup("assign");
    node[1] = strdup($1);
    node[2] = $3;
    node[3] = NULL;
    $$ = node;
}
    ;

print_statement: PRINT LPAREN expression RPAREN NEWLINE {
    void** node = malloc(3 * sizeof(void*));
    node[0] = strdup("print");
    node[1] = $3;
    node[2] = NULL;
    $$ = node;
}
    ;

input_statement: IDENTIFIER ASSIGN INPUT NEWLINE {
    void** node = malloc(3 * sizeof(void*));
    node[0] = strdup("input");
    node[1] = strdup($1);
    node[2] = NULL;
    $$ = node;
}
    | IDENTIFIER ASSIGN INPUT LPAREN RPAREN NEWLINE {
    void** node = malloc(3 * sizeof(void*));
    node[0] = strdup("input");
    node[1] = strdup($1);
    node[2] = NULL;
    $$ = node;
}
    ;

if_statement
    : IF expression block else_clause_opt {
        void** node = malloc(6 * sizeof(void*));
        node[0] = strdup("if");
        node[1] = $2;    // condition
        node[2] = $3;    // then block
        node[3] = NULL;  // no else-if list
        node[4] = $4;    // else clause opt
        node[5] = NULL;  // terminator for print_ast loop
        $$ = node;
    }
    ;
else_clause_opt
    : /* empty */ { $$ = NULL; }
    | ELSE if_statement { $$ = $2; }
    | ELSE block {
        void** node = malloc(3 * sizeof(void*));  // not 2
        node[0] = strdup("else");
        node[1] = $2;
        node[2] = NULL;  // <== THIS LINE FIXES THE SEGFAULT
        $$ = node;
    }
    ;


while_statement: WHILE expression block {
    void** node = malloc(4 * sizeof(void*));
    node[0] = strdup("while");
    node[1] = $2;
    node[2] = $3;
    node[3] = NULL;
    $$ = node;
}
    ;

wait_statement: WAIT LPAREN expression RPAREN NEWLINE {
    void** node = malloc(3 * sizeof(void*));
    node[0] = strdup("wait");
    node[1] = $3;
    node[2] = NULL;
    $$ = node;
}
    ;

save_statement: SAVE LPAREN expression COMMA expression RPAREN NEWLINE {
    void** node = malloc(4 * sizeof(void*));
    node[0] = strdup("save");
    node[1] = $3;
    node[2] = $5;
    node[3] = NULL;
    $$ = node;
}
    ;

block: LBRACE statements RBRACE { $$ = $2; }
    ;

expression: comparison { $$ = $1; }
    ;

comparison: addition { $$ = $1; }
         | addition EQ addition {
             void** node = malloc(4 * sizeof(void*));
             node[0] = strdup("eq");
             node[1] = $1;
             node[2] = $3;
             node[3] = NULL;
             $$ = node;
         }
         | addition NE addition {
             void** node = malloc(4 * sizeof(void*));
             node[0] = strdup("ne");
             node[1] = $1;
             node[2] = $3;
             node[3] = NULL;
             $$ = node;
         }
         | addition LT addition {
             void** node = malloc(4 * sizeof(void*));
             node[0] = strdup("lt");
             node[1] = $1;
             node[2] = $3;
             node[3] = NULL;
             $$ = node;
         }
         | addition GT addition {
             void** node = malloc(4 * sizeof(void*));
             node[0] = strdup("gt");
             node[1] = $1;
             node[2] = $3;
             node[3] = NULL;
             $$ = node;
         }
         | addition LE addition {
             void** node = malloc(4 * sizeof(void*));
             node[0] = strdup("le");
             node[1] = $1;
             node[2] = $3;
             node[3] = NULL;
             $$ = node;
         }
         | addition GE addition {
             void** node = malloc(4 * sizeof(void*));
             node[0] = strdup("ge");
             node[1] = $1;
             node[2] = $3;
             node[3] = NULL;
             $$ = node;
         }
    ;

addition: term { $$ = $1; }
       | addition PLUS term {
           void** node = malloc(4 * sizeof(void*));
           node[0] = strdup("add");
           node[1] = $1;
           node[2] = $3;
           node[3] = NULL;
           $$ = node;
       }
       | addition MINUS term {
           void** node = malloc(4 * sizeof(void*));
           node[0] = strdup("sub");
           node[1] = $1;
           node[2] = $3;
           node[3] = NULL;
           $$ = node;
       }
    ;

term: factor { $$ = $1; }
    | term MULT factor {
        void** node = malloc(4 * sizeof(void*));
        node[0] = strdup("mul");
        node[1] = $1;
        node[2] = $3;
        node[3] = NULL;
        $$ = node;
    }
    | term DIV factor {
        void** node = malloc(4 * sizeof(void*));
        node[0] = strdup("div");
        node[1] = $1;
        node[2] = $3;
        node[3] = NULL;
        $$ = node;
    }
    ;

factor: NUMBER {
        void** node = malloc(3 * sizeof(void*));
        node[0] = strdup("number");
        // Store number in a dynamically allocated int
        int* num = malloc(sizeof(int));
        *num = $1;
        node[1] = num;
        node[2] = NULL;
        $$ = node;
    }
     | STRING {
        void** node = malloc(3 * sizeof(void*));
        node[0] = strdup("string");
        node[1] = strdup($1);
        node[2] = NULL;
        $$ = node;
    }
     | IDENTIFIER {
        void** node = malloc(3 * sizeof(void*));
        node[0] = strdup("identifier");
        node[1] = strdup($1);
        node[2] = NULL;
        $$ = node;
    }
     | INPUT {
        void** node = malloc(2 * sizeof(void*));
        node[0] = strdup("input");
        node[1] = NULL;
        $$ = node;
    }
     | INPUT LPAREN RPAREN {
        void** node = malloc(2 * sizeof(void*));
        node[0] = strdup("input");
        node[1] = NULL;
        $$ = node;
    }
     | TIME LPAREN RPAREN {
        void** node = malloc(2 * sizeof(void*));
        node[0] = strdup("time");
        node[1] = NULL;
        $$ = node;
    }
     | LPAREN expression RPAREN { $$ = $2; }
    ;

%%

void print_ast(void *node, int level) {
    if (node == NULL) return;
    
    void **n = (void**)node;
    char *type = (char*)n[0];
    
    // Print indentation
    for (int i = 0; i < level; i++) printf("  ");
    
    // Handle special nodes first
    if (strcmp(type, "number") == 0) {
        printf("Number: %d\n", *(int*)n[1]);
    }
    else if (strcmp(type, "string") == 0) {
        printf("String: %s\n", (char*)n[1]);
    }
    else if (strcmp(type, "identifier") == 0) {
        printf("Identifier: %s\n", (char*)n[1]);
    }
    else if (strcmp(type, "var_decl") == 0) {
        printf("Variable Declaration:\n");
        for (int i = 0; i < level + 1; i++) printf("  ");
        printf("Name: %s\n", (char*)n[1]);
        print_ast(n[2], level + 1);
    }
    else if (strcmp(type, "assign") == 0) {
        printf("Assignment:\n");
        for (int i = 0; i < level + 1; i++) printf("  ");
        printf("Variable: %s\n", (char*)n[1]);
        print_ast(n[2], level + 1);
    }
    else if (strcmp(type, "print") == 0) {
        printf("Print Statement:\n");
        print_ast(n[1], level + 1);
    }
    else if (strcmp(type, "while") == 0) {
        printf("While Loop:\n");
        for (int i = 0; i < level + 1; i++) printf("  ");
        printf("Condition:\n");
        print_ast(n[1], level + 2);
        for (int i = 0; i < level + 1; i++) printf("  ");
        printf("Body:\n");
        print_ast(n[2], level + 2);
    }
    else if (strcmp(type, "if") == 0) {
        printf("If Statement:\n");
        for (int i = 0; i < level + 1; i++) printf("  ");
        printf("Condition:\n");
        print_ast(n[1], level + 2);
        for (int i = 0; i < level + 1; i++) printf("  ");
        printf("Then:\n");
        print_ast(n[2], level + 2);
        if (n[3] != NULL) {
            for (int i = 0; i < level + 1; i++) printf("  ");
            printf("Else If:\n");
            print_ast(n[3], level + 2);
        }
        if (n[4] != NULL) {
            for (int i = 0; i < level + 1; i++) printf("  ");
            printf("Else:\n");
            print_ast(n[4], level + 2);
        }
    }
    else if (strcmp(type, "else") == 0) {
        printf("Else Clause:\n");
        print_ast(n[1], level + 1);
    }
    else if (strcmp(type, "input") == 0) {
        printf("Input Operation\n");
    }
    else if (strcmp(type, "wait") == 0) {
        printf("Wait Statement:\n");
        print_ast(n[1], level + 1);
    }
    else if (strcmp(type, "save") == 0) {
        printf("Save Statement:\n");
        for (int i = 0; i < level + 1; i++) printf("  ");
        printf("File:\n");
        print_ast(n[1], level + 2);
        for (int i = 0; i < level + 1; i++) printf("  ");
        printf("Content:\n");
        print_ast(n[2], level + 2);
    }
    else if (strcmp(type, "statements") == 0) {
        printf("Statements:\n");
        // Print statements as a list: left then right
        print_ast(n[1], level + 1);
        print_ast(n[2], level + 1);
    }
    else {
        // Generic operator node (add, sub, mul, div, eq, lt, etc.)
        printf("%s\n", type);
        for (int i = 1; n[i] != NULL; i++) {
            print_ast(n[i], level + 1);
        }
    }
}

Value eval_expr(void *node) {
    Value result;
    result.is_string = 0;
    result.int_value = 0;

    if (node == NULL) return result;

    void **n = (void**)node;
    char *type = (char*)n[0];

    if (strcmp(type, "number") == 0) {
        result.is_string = 0;
        result.int_value = *(int*)n[1];
    }
    else if (strcmp(type, "string") == 0) {
        result.is_string = 1;
        result.str_value = strdup((char*)n[1]);
    }
    else if (strcmp(type, "identifier") == 0) {
        result = get_variable((char*)n[1]);
    }
    else if (strcmp(type, "add") == 0) {
        Value left = eval_expr(n[1]);
        Value right = eval_expr(n[2]);

        if (left.is_string || right.is_string) {
            // Convert ints to strings if needed
            char left_str[1000], right_str[1000];
            if (left.is_string) {
                strcpy(left_str, left.str_value);
            } else {
                sprintf(left_str, "%d", left.int_value);
            }
            if (right.is_string) {
                strcpy(right_str, right.str_value);
            } else {
                sprintf(right_str, "%d", right.int_value);
            }

            // Concatenate strings
            char *result_str = malloc(strlen(left_str) + strlen(right_str) + 1);
            strcpy(result_str, left_str);
            strcat(result_str, right_str);

            result.is_string = 1;
            result.str_value = result_str;
        } else {
            // Pure integer addition
            result.is_string = 0;
            result.int_value = left.int_value + right.int_value;
        }
    }
    else if (strcmp(type, "sub") == 0) {
        Value left = eval_expr(n[1]);
        Value right = eval_expr(n[2]);
        result.is_string = 0;
        result.int_value = left.int_value - right.int_value;
    }
    else if (strcmp(type, "mul") == 0) {
        Value left = eval_expr(n[1]);
        Value right = eval_expr(n[2]);
        result.is_string = 0;
        result.int_value = left.int_value * right.int_value;
    }
    else if (strcmp(type, "div") == 0) {
        Value left = eval_expr(n[1]);
        Value right = eval_expr(n[2]);
        result.is_string = 0;
        result.int_value = left.int_value / right.int_value;
    }
    else if (strcmp(type, "lt") == 0) {
        Value left = eval_expr(n[1]);
        Value right = eval_expr(n[2]);
        result.is_string = 0;
        result.int_value = left.int_value < right.int_value;
    }
    else if (strcmp(type, "gt") == 0) {
        Value left = eval_expr(n[1]);
        Value right = eval_expr(n[2]);
        result.is_string = 0;
        result.int_value = left.int_value > right.int_value;
    }
    else if (strcmp(type, "le") == 0) {
        Value left = eval_expr(n[1]);
        Value right = eval_expr(n[2]);
        result.is_string = 0;
        result.int_value = left.int_value <= right.int_value;
    }
    else if (strcmp(type, "ge") == 0) {
        Value left = eval_expr(n[1]);
        Value right = eval_expr(n[2]);
        result.is_string = 0;
        result.int_value = left.int_value >= right.int_value;
    }
    else if (strcmp(type, "eq") == 0) {
        Value left = eval_expr(n[1]);
        Value right = eval_expr(n[2]);
        result.is_string = 0;
        if (left.is_string || right.is_string) {
            // Compare strings
            char *left_str = left.is_string ? left.str_value : "";
            char *right_str = right.is_string ? right.str_value : "";
            result.int_value = strcmp(left_str, right_str) == 0;
        } else {
            result.int_value = left.int_value == right.int_value;
        }
    }
    else if (strcmp(type, "ne") == 0) {
        Value left = eval_expr(n[1]);
        Value right = eval_expr(n[2]);
        result.is_string = 0;
        if (left.is_string || right.is_string) {
            char *left_str = left.is_string ? left.str_value : "";
            char *right_str = right.is_string ? right.str_value : "";
            result.int_value = strcmp(left_str, right_str) != 0;
        } else {
            result.int_value = left.int_value != right.int_value;
        }
    }
    else if (strcmp(type, "input") == 0) {
        char buffer[1000];
        printf("> ");
        fgets(buffer, sizeof(buffer), stdin);
        buffer[strcspn(buffer, "\n")] = 0;  // remove newline

        result.is_string = 1;
        result.str_value = strdup(buffer);
    }
    else if (strcmp(type, "time") == 0) {
        result.is_string = 0;
        result.int_value = (int)time(NULL);
    }

    return result;
}


void eval_ast(void *node) {
    if (node == NULL) return;

    void **n = (void**)node;
    char *type = (char*)n[0];

    if (strcmp(type, "statements") == 0) {
        eval_ast(n[1]);
        eval_ast(n[2]);
    }
    else if (strcmp(type, "var_decl") == 0) {
        char *var_name = (char*)n[1];
        Value value = eval_expr(n[2]);
        set_variable(var_name, value);
    }
    else if (strcmp(type, "assign") == 0) {
        char *var_name = (char*)n[1];
        Value value = eval_expr(n[2]);
        set_variable(var_name, value);
    }
    else if (strcmp(type, "print") == 0) {
        Value value = eval_expr(n[1]);
        if (value.is_string) {
            printf("%s\n", value.str_value);
        } else {
            printf("%d\n", value.int_value);
        }
    }

    else if (strcmp(type, "wait") == 0) {
        Value value = eval_expr(n[1]); 
        int ms = value.int_value;
        usleep(ms * 1000);
    }
    else if (strcmp(type, "save") == 0) {
        Value file_name_val = eval_expr(n[1]);
        Value content_val = eval_expr(n[2]);

        if (!file_name_val.is_string) {
            printf("Error: SAVE file name must be a string.\n");
            return;
        }

        const char *filename = file_name_val.str_value;
        FILE *f = fopen(filename, "w");
        if (!f) {
            printf("Error: could not open file %s for writing.\n", filename);
            return;
        }

        if (content_val.is_string) {
            fprintf(f, "%s", content_val.str_value);
        } else {
            fprintf(f, "%d", content_val.int_value);
        }

        fclose(f);
    }

    else if (strcmp(type, "while") == 0) {
        Value cond = eval_expr(n[1]);
        while (cond.int_value) {
            eval_ast(n[2]);
            cond = eval_expr(n[1]);  // re-evaluate condition
        }
    }
    else if (strcmp(type, "if") == 0) {
        Value cond = eval_expr(n[1]);
        if (cond.int_value) {
            eval_ast(n[2]);
        } else if (n[4] != NULL) {
            void **else_node = (void**)n[4];
            if (strcmp((char*)else_node[0], "else") == 0) {
                eval_ast(else_node[1]);
            } else {
                eval_ast(n[4]);  // else if
            }
        }
    }
}

int codegen_expr(FILE *out, void *node) {
    if (node == NULL) return -1;

    void **n = (void**)node;
    char *type = (char*)n[0];

    if (strcmp(type, "number") == 0) {
        int value = *(int*)n[1];
        int tmp_id = tmp_counter++;
        fprintf(out, "%%%d = add i32 %d, 0\n", tmp_id, value);
        return tmp_id;
    }
    else if (strcmp(type, "identifier") == 0) {
        char *var_name = (char*)n[1];
        int tmp_id = tmp_counter++;
        fprintf(out, "%%%d = load i32, i32* %%%s\n", tmp_id, var_name);
        return tmp_id;
    }
    else if (strcmp(type, "string") == 0) {
        char *str = (char*)n[1];
        const char *str_name = codegen_string_literal(header_out, str);
        int tmp_id = tmp_counter++;
        fprintf(out, "%%%d = getelementptr inbounds [%zu x i8], [%zu x i8]* @%s, i64 0, i64 0\n", 
                tmp_id, strlen(str)+1, strlen(str)+1, str_name);
        return tmp_id;
    }
    else if (strcmp(type, "add") == 0) {
        int left = codegen_expr(out, n[1]);
        int right = codegen_expr(out, n[2]);
        int tmp_id = tmp_counter++;
        fprintf(out, "%%%d = add i32 %%%d, %%%d\n", tmp_id, left, right);
        return tmp_id;
    }
    else if (strcmp(type, "sub") == 0) {
        int left = codegen_expr(out, n[1]);
        int right = codegen_expr(out, n[2]);
        int tmp_id = tmp_counter++;
        fprintf(out, "%%%d = sub i32 %%%d, %%%d\n", tmp_id, left, right);
        return tmp_id;
    }
    else if (strcmp(type, "mul") == 0) {
        int left = codegen_expr(out, n[1]);
        int right = codegen_expr(out, n[2]);
        int tmp_id = tmp_counter++;
        fprintf(out, "%%%d = mul i32 %%%d, %%%d\n", tmp_id, left, right);
        return tmp_id;
    }
    else if (strcmp(type, "div") == 0) {
        int left = codegen_expr(out, n[1]);
        int right = codegen_expr(out, n[2]);
        int tmp_id = tmp_counter++;
        fprintf(out, "%%%d = sdiv i32 %%%d, %%%d\n", tmp_id, left, right);
        return tmp_id;
    }
    else if (strcmp(type, "input") == 0) {
        // Proteção extra:
        if (n[1] != NULL) {
            // input_statement → NÃO entra aqui
            fprintf(stderr, "ERROR: codegen_expr: input_statement detected in expression context!\n");
            exit(1);
        }

        int tmp_id = tmp_counter++;
        fprintf(out, "%%%d = call i32 @my_input()\n", tmp_id);
        return tmp_id;
    }
    else if (strcmp(type, "time") == 0) {
        int tmp_id = tmp_counter++;
        fprintf(out, "%%%d = call i32 @time(i32* null)\n", tmp_id);
        return tmp_id;
    }
    else if (strcmp(type, "lt") == 0) {
        int left = codegen_expr(out, n[1]);
        int right = codegen_expr(out, n[2]);
        int tmp_id_cmp = tmp_counter++;
        int tmp_id_bool = tmp_counter++;
        fprintf(out, "%%%d = icmp slt i32 %%%d, %%%d\n", tmp_id_cmp, left, right);
        fprintf(out, "%%%d = zext i1 %%%d to i32\n", tmp_id_bool, tmp_id_cmp);
        return tmp_id_bool;
    }
    else if (strcmp(type, "eq") == 0) {
        int left = codegen_expr(out, n[1]);
        int right = codegen_expr(out, n[2]);
        int tmp_id_cmp = tmp_counter++;
        int tmp_id_bool = tmp_counter++;
        fprintf(out, "%%%d = icmp eq i32 %%%d, %%%d\n", tmp_id_cmp, left, right);
        fprintf(out, "%%%d = zext i1 %%%d to i32\n", tmp_id_bool, tmp_id_cmp);
        return tmp_id_bool;
    }
    else {
        fprintf(stderr, "ERROR: codegen_expr: unsupported node type: %s\n", type);
        return -1;
    }
}



char* codegen_expr_string(FILE *out, void *node) {
    if (!node) return NULL;
    void **n = (void**)node;
    char *type = (char*)n[0];

    // string literal
    if (strcmp(type,"string")==0) {
        char *s=(char*)n[1];
        const char *nm = codegen_string_literal(header_out, s);
        int r=tmp_counter++;
        fprintf(out,
          "%%%d = getelementptr inbounds [%zu x i8], [%zu x i8]* @%s, i64 0, i64 0\n",
          r, strlen(s)+1, strlen(s)+1, nm);
        char *name=malloc(16);
        sprintf(name,"%%%d",r);
        return name;
    }
    // identifier → string via sprintf
    if (strcmp(type,"identifier")==0) {
        char *v=(char*)n[1];
        int load=tmp_counter++;
        fprintf(out,"%%%d = load i32, i32* %%%s\n",load,v);
        int buf=tmp_counter++;
        fprintf(out,"%%%d = alloca [32 x i8], align 1\n",buf);
        int gep=tmp_counter++;
        fprintf(out,
          "%%%d = getelementptr inbounds [32 x i8], [32 x i8]* %%%d, i64 0, i64 0\n",
          gep, buf);
        int call=tmp_counter++;
        fprintf(out,
          "%%%d = call i32 @sprintf(i8* %%%d, i8* getelementptr inbounds ([4 x i8],[4 x i8]* @.fmt,i64 0,i64 0), i32 %%%d)\n",
          call, gep, load);
        char *name=malloc(16);
        sprintf(name,"%%%d",gep);
        return name;
    }
    // number → string
    if (strcmp(type,"number")==0) {
        int v = *(int*)n[1];
        int buf=tmp_counter++;
        fprintf(out,"%%%d = alloca [32 x i8], align 1\n",buf);
        int gep=tmp_counter++;
        fprintf(out,
          "%%%d = getelementptr inbounds [32 x i8], [32 x i8]* %%%d, i64 0, i64 0\n",
          gep, buf);
        int call=tmp_counter++;
        fprintf(out,
          "%%%d = call i32 @sprintf(i8* %%%d, i8* getelementptr inbounds ([4 x i8],[4 x i8]* @.fmt,i64 0,i64 0), i32 %d)\n",
          call, gep, v);
        char *name=malloc(16);
        sprintf(name,"%%%d",gep);
        return name;
    }
    // input → string
    if (strcmp(type,"input")==0) {
        int call_id = tmp_counter++;
        fprintf(out,"%%%d = call i32 @my_input()\n",call_id);
        int buf = tmp_counter++;
        fprintf(out,"%%%d = alloca [32 x i8], align 1\n",buf);
        int gep = tmp_counter++;
        fprintf(out,
          "%%%d = getelementptr inbounds [32 x i8], [32 x i8]* %%%d, i64 0, i64 0\n",
          gep, buf);
        int call = tmp_counter++;
        fprintf(out,
          "%%%d = call i32 @sprintf(i8* %%%d, i8* getelementptr inbounds ([4 x i8],[4 x i8]* @.fmt,i64 0,i64 0), i32 %%%d)\n",
          call, gep, call_id);
        char *name=malloc(16);
        sprintf(name,"%%%d",gep);
        return name;
    }
    // add strings
    if (strcmp(type,"add")==0) {
        char *L=codegen_expr_string(out,n[1]);
        char *R=codegen_expr_string(out,n[2]);
        int buf=tmp_counter++;
        fprintf(out,"%%%d = alloca [256 x i8], align 1\n",buf);
        int gep=tmp_counter++;
        fprintf(out,
          "%%%d = getelementptr inbounds [256 x i8], [256 x i8]* %%%d, i64 0, i64 0\n",
          gep, buf);
        fprintf(out,"call void @concat_strings(i8* %%%d, i8* %s, i8* %s)\n",gep,L,R);
        char *name=malloc(16);
        sprintf(name,"%%%d",gep);
        return name;
    }
    fprintf(stderr,"unsupported in codegen_expr_string: %s\n",type);
    return NULL;
}


void codegen(FILE *out, void *node) {
    if (node == NULL) return;

    void **n = (void**)node;
    char *type = (char*)n[0];

    if (strcmp(type, "statements") == 0) {
        codegen(out, n[1]);
        codegen(out, n[2]);
    }
    else if (strcmp(type, "var_decl") == 0) {
        char *var_name = (char*)n[1];
        fprintf(out, "%%%s = alloca i32\n", var_name);
        int v = codegen_expr(out, n[2]);
        fprintf(out, "store i32 %%%d, i32* %%%s\n", v, var_name);
    }
    else if (strcmp(type, "assign") == 0) {
        char *var_name = (char*)n[1];
        int v = codegen_expr(out, n[2]);
        fprintf(out, "store i32 %%%d, i32* %%%s\n", v, var_name);
    }
    else if (strcmp(type, "print") == 0) {
        if (strcmp(((char**)n[1])[0], "string") == 0 ||
            strcmp(((char**)n[1])[0], "identifier") == 0 ||
            strcmp(((char**)n[1])[0], "add") == 0) {

            char* str_id = codegen_expr_string(out, n[1]);
            int call = tmp_counter++;
            fprintf(out, "%%%d = call i32 @printf(i8* getelementptr inbounds ([3 x i8], [3 x i8]* @.fmt_str, i32 0, i32 0), i8* %s)\n", 
                    call, str_id);
        }
        else {
            int tmp_id = codegen_expr(out, n[1]);
            int call = tmp_counter++;
            fprintf(out, "%%%d = call i32 @printf(i8* getelementptr inbounds ([4 x i8], [4 x i8]* @.fmt, i32 0, i32 0), i32 %%%d)\n", 
                    call, tmp_id);
        }
    }
    else if (strcmp(type, "wait") == 0) {
        int tmp_id = codegen_expr(out, n[1]);
        fprintf(out, "call void @sleep_ms(i32 %%%d)\n", tmp_id);
    }
    else if (strcmp(type, "input") == 0 && n[1] != NULL) {
        // é um input_statement
        char *var_name = (char*)n[1];
        int tmp_id = tmp_counter++;
        fprintf(out, "%%%d = call i32 @my_input()\n", tmp_id);
        fprintf(out, "store i32 %%%d, i32* %%%s\n", tmp_id, var_name);
    }
    else if (strcmp(type, "save") == 0) {
        // Gerar os dois argumentos como string:
        char* file_str_id = codegen_expr_string(out, n[1]);
        char* content_str_id = codegen_expr_string(out, n[2]);

        // Gerar a chamada:
        fprintf(out, "call void @save_file(i8* %s, i8* %s)\n", file_str_id, content_str_id);
    }
    else if (strcmp(type, "if") == 0) {
        static int label_count = 0;
        int curr = label_count++;

        int cond_id = codegen_expr(out, n[1]);
        int cmp_id = tmp_counter++;
        fprintf(out, "%%%d = icmp ne i32 %%%d, 0\n", cmp_id, cond_id);
        fprintf(out, "br i1 %%%d, label %%if_then_%d, label %%if_else_%d\n", cmp_id, curr, curr);

        fprintf(out, "if_then_%d:\n", curr);
        codegen(out, n[2]);
        fprintf(out, "br label %%if_end_%d\n", curr);

        fprintf(out, "if_else_%d:\n", curr);
        if (n[4] != NULL) {
            codegen(out, n[4]);
        }
        fprintf(out, "br label %%if_end_%d\n", curr);

        fprintf(out, "if_end_%d:\n", curr);
    }
    else if (strcmp(type, "while") == 0) {
        static int label_count = 0;
        int curr = label_count++;

        fprintf(out, "br label %%while_cond_%d\n", curr);
        fprintf(out, "while_cond_%d:\n", curr);

        int cond_id = codegen_expr(out, n[1]);
        int cmp_id = tmp_counter++;
        fprintf(out, "%%%d = icmp ne i32 %%%d, 0\n", cmp_id, cond_id);
        fprintf(out, "br i1 %%%d, label %%while_body_%d, label %%while_end_%d\n", cmp_id, curr, curr);

        fprintf(out, "while_body_%d:\n", curr);
        codegen(out, n[2]);
        fprintf(out, "br label %%while_cond_%d\n", curr);

        fprintf(out, "while_end_%d:\n", curr);
    }
}


void yyerror(char *s) {
    fprintf(stderr, "Line %d: Syntax error: %s\n", line_num, s);
    fprintf(stderr, "Unexpected token: %s\n", yytext);
    fprintf(stderr, "Current line: %d\n", line_num);
}



int main(int argc, char **argv) {
    if (argc > 1) {
        yyin = fopen(argv[1], "r");
        if (!yyin) {
            fprintf(stderr, "Could not open input file: %s\n", argv[1]);
            return 1;
        } else {
            fprintf(stderr, "Opened input file: %s\n", argv[1]);
        }
    } else {
        yyin = stdin;
    }

    printf("Starting parse...\n");
    yyparse();
    printf("Parse completed.\n");

    printf("Executing program...\n");
    eval_ast(global_ast);
    printf("Program finished.\n");

    FILE *out = fopen("program.ll", "w");
    header_out = out;

    // 1️⃣ Declarações
    fprintf(out, "declare i32 @printf(i8*, i8*)\n");
    fprintf(out, "declare i32 @my_input()\n");
    fprintf(out, "declare void @sleep_ms(i32)\n");
    fprintf(out, "declare void @save_file(i8*, i8*)\n");
    fprintf(out, "declare i32 @sprintf(i8*, i8*, i32)\n");
    fprintf(out, "declare void @concat_strings(i8*, i8*, i8*)\n");
    fprintf(out, "declare i32 @time(i32*)\n");

    // 2️⃣ Constantes globais
    fprintf(out, "@.fmt = private unnamed_addr constant [4 x i8] c\"%%d\\0A\\00\"\n");
    fprintf(out, "@.fmt_str = private unnamed_addr constant [3 x i8] c\"%%s\\00\"\n");

    // 3️⃣ Emit collected string literals
    for (int i = 0; i < string_literal_count; i++) {
        const char *s = string_literals[i];
        size_t len = strlen(s) + 1;
        fprintf(out,
            "@str_%d = private unnamed_addr constant [%zu x i8] c\"%s\\00\"\n",
            i, len, escape_string_for_llvm(s));
    }

    // 4️⃣ Define main
    fprintf(out, "define i32 @main() {\nentry:\n");

    // 5️⃣ Gera o corpo do programa
    codegen(out, global_ast);

    // 6️⃣ Fecha main
    fprintf(out, "ret i32 0\n}\n");

    // 7️⃣ Limpeza
    for (int i = 0; i < string_literal_count; i++) {
        free(string_literals[i]);
    }

    fclose(out);

    return 0;
}


