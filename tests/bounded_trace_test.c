#include "../runtime/bounded_trace.h"
#include <assert.h>
static void rows(BoundedTrace *t) {
    bt_row(t, 0, t->rows[0] + 1, 1);
    bt_row(t, 1, t->rows[1] + 1, 1);
}
int main(void) {
    FILE *f = tmpfile(); char text[1024]; size_t n;
    BoundedTrace t = {0}; assert(f);
    assert(bt_target("120") == 120 && bt_target("0") == -1);
    assert(bt_target("-1") == -1 && bt_target("12garbage") == -1);
    assert(bt_target("9999999999999999999999") == -1);
    t.target = 2;
    bt_boundary(&t, f, '?', 0); assert(!t.passes);
    rows(&t); bt_boundary(&t, f, 'R', 0);
    rows(&t); bt_boundary(&t, f, 'S', 1); assert(t.real == 1 && !t.state);
    rows(&t); bt_boundary(&t, f, 'R', 0); assert(t.state == 1);
    long end = ftell(f);
    rows(&t); bt_boundary(&t, f, 'R', 0); assert(ftell(f) == end);
    rewind(f); n = fread(text, 1, sizeof text - 1, f); text[n] = 0;
    assert(strstr(text, "TRACE_PASS 2 S\n"));
    assert(strstr(text, "TRACE_END diagnostic=1 target=2 real=2 passes=3 rows0=3 rows1=3 pending=0\n"));
    fclose(f);
    f = tmpfile(); assert(f);
    memset(&t, 0, sizeof t); t.target = 1; rows(&t);
    bt_boundary(&t, f, 'R', 1); assert(t.state == -1 && !strcmp(t.failure, "pending_replay"));
    memset(&t, 0, sizeof t); t.target = 1; t.active = 1; rows(&t);
    bt_boundary(&t, f, 'R', 0); assert(t.state == -1 && !strcmp(t.failure, "active_writer"));
    memset(&t, 0, sizeof t); t.target = 1; rows(&t); rows(&t);
    bt_boundary(&t, f, 'R', 0); assert(t.state == -1 && !strcmp(t.failure, "row_coverage"));
    memset(&t, 0, sizeof t); t.target = 1;
    bt_boundary(&t, f, 'R', 0); assert(t.state == -1 && !strcmp(t.failure, "missing_rows"));
    memset(&t, 0, sizeof t); t.target = 1; rows(&t);
    bt_boundary(&t, f, 0, 0); assert(t.state == -1 && !strcmp(t.failure, "kind_coverage"));
    memset(&t, 0, sizeof t); t.target = 1; t.real = 1; rows(&t);
    bt_boundary(&t, f, 'R', 0); assert(t.state == -1 && !strcmp(t.failure, "overshoot"));
    memset(&t, 0, sizeof t); t.target = 1;
    bt_row(&t, 0, 1, 0); assert(t.state == -1 && !strcmp(t.failure, "write"));
    memset(&t, 0, sizeof t); t.target = 1; rows(&t);
    bt_boundary(&t, NULL, 'R', 0); assert(t.state == -1);
    /* A producer collected before exit must not write after stream closure. */
    memset(&t, 0, sizeof t); t.target = 1; t.active = 1;
    assert(bt_can_write(&t, f));
    bt_fail(&t, "shutdown");
    assert(!bt_can_write(&t, NULL));
    bt_row(&t, 0, 1, 1); assert(!t.rows[0]);
    bt_boundary(&t, NULL, 'R', 0);
    assert(t.state == -1 && !strcmp(t.failure, "shutdown"));
    memset(&t, 0, sizeof t); t.target = 1;
    assert(!bt_can_write(&t, NULL) && t.state == -1);
    memset(&t, 0, sizeof t); t.state = 1;
    bt_fail(&t, "shutdown"); assert(t.state == 1 && !bt_can_write(&t, NULL));
    fclose(f);
    puts("bounded diagnostic trace contract: PASS");
    return 0;
}
