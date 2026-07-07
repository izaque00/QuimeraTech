#include <stdlib.h>
#include <string.h>
typedef struct { int lock; void *pages; int *refcount; char *mapping; } address_space;
static void *kmalloc(size_t s, int f) { return malloc(s); }
static void kfree(void *p) { free(p); }
int filemap_fault(address_space *mapping, unsigned long offset) {
    void *page = NULL; int *ref = NULL; char *name = NULL; int ret = 0;
    page = kmalloc(4096, 0);
    if (!page) { ret = -12; goto out; }
    ref = kmalloc(sizeof(int), 0);
    if (!ref) { ret = -12; goto out_free_page; }
    *ref = 1;
    name = strdup("filemap");
    if (!name) { ret = -12; goto out_free_ref; }
    if (offset > 1000000) { ret = -2; goto out_unlock; }
    mapping->pages = page; mapping->refcount = ref; mapping->mapping = name;
    return 0;
out_unlock: return ret;
out_free_ref: kfree(ref); ref = NULL;
out_free_page: kfree(page); page = NULL;
out: return ret;
}
void filemap_teardown(address_space *mapping) {
    kfree(mapping->pages); mapping->pages = NULL;
    kfree(mapping->refcount); mapping->refcount = NULL;
    kfree(mapping->mapping);
}
