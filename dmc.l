%{
#include <stdio.h>
#include <stdlib.h>
#include "dmc.tab.h"

void yyerror(char *);
int line_num = 1;
%}

%%
[ \t]           ; /* ignore whitespace */
\n              { line_num++; return NEWLINE; }
#.*             ; /* ignore comments */
"var"           { printf("Found VAR token\n"); return VAR; }
"if"            { printf("Found IF token\n"); return IF; }
"else"          { printf("Found ELSE token\n"); return ELSE; }
"while"         { printf("Found WHILE token\n"); return WHILE; }
"print"         { printf("Found PRINT token\n"); return PRINT; }
"input"         { printf("Found INPUT token\n"); return INPUT; }
"wait"          { printf("Found WAIT token\n"); return WAIT; }
"save"          { printf("Found SAVE token\n"); return SAVE; }
"time"          { printf("Found TIME token\n"); return TIME; }
"=="            { printf("Found EQ token\n"); return EQ; }
"!="            { printf("Found NE token\n"); return NE; }
"<="            { printf("Found LE token\n"); return LE; }
">="            { printf("Found GE token\n"); return GE; }
"<"             { printf("Found LT token\n"); return LT; }
">"             { printf("Found GT token\n"); return GT; }
"="             { printf("Found ASSIGN token\n"); return ASSIGN; }
"+"             { printf("Found PLUS token\n"); return PLUS; }
"-"             { printf("Found MINUS token\n"); return MINUS; }
"*"             { printf("Found MULT token\n"); return MULT; }
"/"             { printf("Found DIV token\n"); return DIV; }
"{"             { printf("Found LBRACE token\n"); return LBRACE; }
"}"             { printf("Found RBRACE token\n"); return RBRACE; }
"("             { printf("Found LPAREN token\n"); return LPAREN; }
")"             { printf("Found RPAREN token\n"); return RPAREN; }
","             { printf("Found COMMA token\n"); return COMMA; }
[0-9]+          { yylval.num = atoi(yytext); printf("Found NUMBER token: %d\n", yylval.num); return NUMBER; }
[a-zA-Z][a-zA-Z0-9_]*  { 
    printf("Found identifier: %s\n", yytext);
    yylval.id = strdup(yytext); 
    return IDENTIFIER; 
}
\"[^\"]*\"      { 
    // Remove the quotes from the string
    char* str = strdup(yytext);
    str[strlen(str)-1] = '\0';
    yylval.str = str + 1;
    printf("Found STRING token: %s\n", yylval.str);
    return STRING; 
}
.               { 
    fprintf(stderr, "Line %d: Unexpected character: %s\n", line_num, yytext);
    return yytext[0];
}
%%

int yywrap(void) {
    return 1;
} 