#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

int my_input() {
    int x;
    printf("> ");
    scanf("%d", &x);
    return x;
}

void concat_strings(char *dest, const char *s1, const char *s2) {
    strcpy(dest, s1);
    strcat(dest, s2);
}
void sleep_ms(int ms) {
    usleep(ms * 1000);
}

void save_file(const char *filename, const char *content) {
    FILE *f = fopen(filename, "w");
    if (f) {
        fprintf(f, "%s", content);
        fclose(f);
    }
}
