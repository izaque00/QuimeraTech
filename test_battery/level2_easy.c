#include <stdlib.h>
#include <stdio.h>
void handle_buffer() {
    char *buf = malloc(256);
    snprintf(buf, 256, "processing data");
    free(buf);
    printf("%s", buf);  /* CWE-416: use after free */
}
