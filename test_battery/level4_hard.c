#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#define MAX_NAME 64
#define SAFE_FREE(p) do { if (p) { free(p); p = NULL; } } while(0)
typedef struct { char name[MAX_NAME]; char *dynamic_name; void *opaque; int refcount; } Config;
Config *create_config(const char *name) {
    Config *c = malloc(sizeof(Config));
    strncpy(c->name, name, MAX_NAME);
    c->dynamic_name = strdup(name);
    c->opaque = malloc(1024);
    c->refcount = 1; return c;
}
void cleanup_config(Config *c) {
    if (c->refcount > 0) { c->refcount--; return; }
    free(c->dynamic_name); SAFE_FREE(c->opaque);
    free(c);
}
void process(Config *c) {
    char buf[32];
    sprintf(buf, "%s", c->dynamic_name);
    if (c->opaque) { SAFE_FREE(c->opaque); }
    printf("config: %s", c->name);
}
