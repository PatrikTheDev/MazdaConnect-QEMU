/* ABI/state tests for the exact assembly used in the optional firmware patch. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

struct context { uint32_t app, context; };
static struct context ctx;
static int expected_argument, context_calls, events;
extern void state_hook(int, int, int);
extern int finish_hook(void *, struct context *, void *, void *, void *);
asm(".data\n.balign 4\n.global state_storage\nstate_storage: .word 0\n"
    ".text\n.arm\n.global state_continue\nstate_continue: pop {r4,r5,pc}\n");
int set_app_context(void *a, struct context *b, void *c, void *d, void *e) {
    assert(a == &expected_argument && b == &ctx && c == a && d == a && e == a);
    context_calls++;
    return 123;
}
void send_event(int event, int destination) {
    assert(context_calls > 0 && event == 1491 && destination == 1);
    events++;
}
static void finish(int context, int wanted) {
    ctx.context = context;
    int before = context_calls;
    events = 0;
    assert(finish_hook(&expected_argument, &ctx, &expected_argument,
                       &expected_argument, &expected_argument) == 123);
    assert(context_calls == before + 1 && events == wanted);
}
int main(void) {
    finish(1023, 0);  /* unknown system state must not advance the UI */
    state_hook(0, 1, 2);
    finish(1023, 1);  /* Normal plus still in IntroAnimation */
    finish(1012, 0);  /* already displaying Disclaimer */
    state_hook(0, 2, 3);
    finish(1023, 0);  /* later state notification invalidates Normal */
    puts("Intro patch ARM ABI and state conditions passed");
}
