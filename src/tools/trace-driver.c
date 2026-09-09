/* Main-thread ARM syscall trace for vendor startup; does not alter results. */
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ptrace.h>
#include <sys/types.h>
#include <sys/user.h>
#include <sys/wait.h>
#include <unistd.h>

static void path(pid_t pid, unsigned long address, char *out, size_t size) {
    size_t pos = 0;
    while (pos + sizeof(long) < size) {
        errno = 0;
        long word = ptrace(PTRACE_PEEKDATA, pid, (void *)(address + pos), 0);
        if (errno) break;
        for (size_t n = 0; n < sizeof(long); ++n) {
            out[pos++] = (word >> (n * 8)) & 255;
            if (!out[pos - 1]) return;
        }
    }
    out[pos] = 0;
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    pid_t pid = fork();
    if (pid < 0) { perror("fork"); return 2; }
    if (!pid) {
        if (ptrace(PTRACE_TRACEME, 0, 0, 0)) _exit(126);
        raise(SIGSTOP);
        execv(argv[1], argv + 1);
        _exit(127);
    }
    int status, entering = 1, deliver = 0, selected = 0;
    unsigned long call = 0;
    if (waitpid(pid, &status, 0) < 0 ||
        ptrace(PTRACE_SETOPTIONS, pid, 0, PTRACE_O_TRACESYSGOOD | PTRACE_O_TRACEEXEC)) return 2;
    for (;;) {
        if (ptrace(PTRACE_SYSCALL, pid, 0, deliver)) { perror("ptrace"); return 2; }
        if (waitpid(pid, &status, 0) < 0) { perror("waitpid"); return 2; }
        if (WIFEXITED(status)) return WEXITSTATUS(status);
        if (WIFSIGNALED(status)) return 128 + WTERMSIG(status);
        deliver = 0;
        int sig = WSTOPSIG(status);
        if ((unsigned)status >> 16 == PTRACE_EVENT_EXEC) continue;
        struct user_regs regs;
        if (ptrace(PTRACE_GETREGS, pid, 0, &regs)) return 2;
        if (sig == (SIGTRAP | 0x80)) {
            if (entering) {
                call = regs.uregs[7];
                selected = call == 5 || call == 322 || call == 54 || call == 33;
                if (call == 5 || call == 322 || call == 33) {
                    char name[512];
                    path(pid, regs.uregs[call == 322 ? 1 : 0], name, sizeof(name));
                    fprintf(stderr, "TRACE syscall=%lu path=%s", call, name);
                } else if (call == 54) {
                    fprintf(stderr, "TRACE ioctl fd=%lu request=0x%lx", regs.uregs[0], regs.uregs[1]);
                }
            } else if (selected) {
                fprintf(stderr, " result=%ld\n", (long)regs.uregs[0]);
            }
            entering = !entering;
        } else {
            fprintf(stderr, "TRACE signal=%d pc=0x%lx r0=0x%lx r3=0x%lx\n",
                    sig, regs.uregs[15], regs.uregs[0], regs.uregs[3]);
            deliver = sig;
        }
    }
}
