CC = gcc
CFLAGS = -Wall -g

all: dmc

dmc: dmc.l dmc.y
	@echo "Generating parser..."
	bison -d dmc.y
	@echo "Generating lexer..."
	flex dmc.l
	@echo "Compiling..."
	$(CC) $(CFLAGS) -o dmc lex.yy.c dmc.tab.c
	@echo "Done!"

clean:
	rm -f dmc lex.yy.c dmc.tab.c dmc.tab.h

.PHONY: all clean 