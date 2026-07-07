#include <stdlib.h>
#include <string.h>
struct session { char *data; int fd; };
int process_session(struct session *s, const char *input) {
    s->data = strdup(input);
    if (!s->data) return -1;
    if (s->fd < 0) { free(s->data); return -2; }
    if (strlen(s->data) > 1000) { free(s->data); return -3; }
    free(s->data); s->data = NULL;
    return 0;
}
