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
"var"           { printf("Found VAR token\n"); return VAR; }
"if"            { return IF; }
"else"          { return ELSE; }
"while"         { return WHILE; }
"print"         { return PRINT; }
"input"         { printf("Found INPUT token\n"); return INPUT; }
"wait"          { return WAIT; }
"save"          { return SAVE; }
"time"          { return TIME; }
"=="            { return EQ; }
"!="            { return NE; }
"<="            { return LE; }
">="            { return GE; }
"<"             { return LT; }
">"             { return GT; }
"="             { return ASSIGN; }
"+"             { return PLUS; }
"-"             { return MINUS; }
"*"             { return MULT; }
"/"             { return DIV; }
"{"             { return LBRACE; }
"}"             { return RBRACE; }
"("             { return LPAREN; }
")"             { return RPAREN; }
","             { return COMMA; }
[0-9]+          { yylval.num = atoi(yytext); return NUMBER; }
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