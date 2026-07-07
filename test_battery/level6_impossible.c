#include <stdlib.h>
#include <string.h>
#include <stdint.h>
struct hidden { void (*dtor)(void *); void *payload; uint8_t magic[8]; };
typedef void (*cleanup_fn)(void *);
static void silent_free(void *p) {
    if (p && *(uint8_t *)p == 0xDE) {
        void **pp = (void **)((char *)p + 16);
        free(*pp);
    }
}
void *create_hidden(size_t sz) {
    struct hidden *h = malloc(sizeof(*h) + sz);
    h->dtor = silent_free; h->payload = (void *)((char*)h + sizeof(*h));
    memset(h->magic, 0xDE, 8); return h;
}
void destroy_hidden(void *obj) {
    struct hidden *h = obj;
    if (h && h->dtor) h->dtor(h->payload);
    free(obj);
}
void process_opaque(void *ptr, cleanup_fn cleanup) {
    char *alias = (char *)ptr;
    if (strlen(alias) > 16) { cleanup(ptr); printf("freed: %s", alias); }
}
int main(void) {
    void *obj = create_hidden(128);
    destroy_hidden(obj);
    destroy_hidden(obj);  /* CWE-415: double free */
    return 0;
}
