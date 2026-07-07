#include <stdio.h>
#include <stdlib.h>
int process_data(int *ptr) {
    printf("%d", *ptr);  /* CWE-476: ptr could be NULL */
    return 0;
}
