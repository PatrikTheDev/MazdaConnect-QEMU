/* Briefly sample an ARM process without changing registers or signal policy. */
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ptrace.h>
#include <sys/user.h>
#include <sys/wait.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    char *end;
    long number = strtol(argv[1], &end, 10);
    if (*end || number <= 1) return 2;
    pid_t pid = number;
    setvbuf(stdout, NULL, _IONBF, 0);
    for (unsigned sample = 0; sample < 70; ++sample) {
        sleep(1);
        if (ptrace(PTRACE_ATTACH, pid, 0, 0)) {
            if (errno == ESRCH) return 0;
            perror("sample attach"); return 1;
        }
        int status;
        if (waitpid(pid, &status, 0) < 0) { perror("sample wait"); return 1; }
        if (!WIFSTOPPED(status)) return 0;
        struct user_regs regs;
        int ok = !ptrace(PTRACE_GETREGS, pid, 0, &regs);
        if (ok) {
            printf("SAMPLE %u",sample);
            for (unsigned r=0; r<17; ++r) printf(" r%u=%08lx",r,regs.uregs[r]);
            putchar('\n');
            for (unsigned word=0; word<48; ++word) {
                unsigned long address=regs.uregs[13]+word*4;
                errno=0;
                long value=ptrace(PTRACE_PEEKDATA,pid,(void *)address,0);
                if (errno) break;
                printf("STACK %08lx %08lx\n",address,(unsigned long)value);
            }
        }
        int deliver = WSTOPSIG(status) == SIGSTOP ? 0 : WSTOPSIG(status);
        if (ptrace(PTRACE_DETACH,pid,0,deliver)) { perror("sample detach"); return 1; }
        if (!ok) { perror("sample registers"); return 1; }
        if (sample % 10 == 0) {
            char path[64], line[1024];
            snprintf(path,sizeof(path),"/proc/%ld/maps",number);
            FILE *maps=fopen(path,"r");
            if (maps) {
                while (fgets(line,sizeof(line),maps)) printf("MAP %s",line);
                fclose(maps);
            }
        }
    }
    return 0;
}
