/* Briefly sample an ARM process without changing registers or signal policy. */
#include <errno.h>
#include <dirent.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ptrace.h>
#include <sys/user.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* Optional diagnostic: sample only Mesa raster workers, after main detach. */
static int sample_worker(long tid, unsigned sample) {
    if (ptrace(PTRACE_ATTACH,tid,0,0)) {
        if (errno==ESRCH) return 0;
        perror("worker attach"); return -1;
    }
    int status;
    if (waitpid(tid,&status,__WALL)<0) { perror("worker wait"); return -1; }
    if (!WIFSTOPPED(status)) return 0;
    struct user_regs regs;
    int ok=!ptrace(PTRACE_GETREGS,tid,0,&regs);
    if (ok) {
        struct timespec wall,mono;
        if (!clock_gettime(CLOCK_REALTIME,&wall) && !clock_gettime(CLOCK_MONOTONIC,&mono))
            printf("WORKER sample=%u tid=%ld wall=%ld.%09ld mono=%ld.%09ld pc=%08lx lr=%08lx sp=%08lx\n",
                   sample,tid,(long)wall.tv_sec,wall.tv_nsec,(long)mono.tv_sec,mono.tv_nsec,
                   regs.uregs[15],regs.uregs[14],regs.uregs[13]);
        char path[64],line[1024];
        snprintf(path,sizeof(path),"/proc/%ld/maps",tid);
        FILE *maps=fopen(path,"r");
        if (maps) {
            unsigned long first,last;
            while (fgets(line,sizeof(line),maps))
                if (sscanf(line,"%lx-%lx",&first,&last)==2 && regs.uregs[15]>=first && regs.uregs[15]<last)
                    printf("WORKER_MAP sample=%u tid=%ld %s",sample,tid,line);
            fclose(maps);
        }
    }
    int deliver=WSTOPSIG(status)==SIGSTOP ? 0 : WSTOPSIG(status);
    if (ptrace(PTRACE_DETACH,tid,0,deliver)) { perror("worker detach"); return -1; }
    if (!ok) { perror("worker registers"); return -1; }
    return 0;
}

/* Read scheduling evidence after detach. Worker stopping is explicitly opt-in. */
static int thread_activity(long pid, unsigned sample, int workers) {
    char directory[64], path[128], line[2048];
    snprintf(directory,sizeof(directory),"/proc/%ld/task",pid);
    DIR *tasks=opendir(directory);
    if (!tasks) return 0;
    struct dirent *entry;
    while ((entry=readdir(tasks))) {
        char *end;
        long tid=strtol(entry->d_name,&end,10);
        if (*end || tid<=0) continue;
        snprintf(path,sizeof(path),"%s/%ld/stat",directory,tid);
        FILE *file=fopen(path,"r");
        if (file) {
            int raster=0;
            if (fgets(line,sizeof(line),file)) {
                printf("THREAD sample=%u %s",sample,line);
                char *name=strchr(line,'(');
                raster=name && !strncmp(name+1,"llvmpipe-",9);
            }
            fclose(file);
            if (workers && raster && sample_worker(tid,sample)) { closedir(tasks); return -1; }
        }
    }
    closedir(tasks);
    return 0;
}

int main(int argc, char **argv) {
    if (argc!=2 && (argc!=3 || strcmp(argv[2],"--workers"))) return 2;
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
            struct timespec wall, mono;
            if (!clock_gettime(CLOCK_REALTIME,&wall) && !clock_gettime(CLOCK_MONOTONIC,&mono))
                printf("TIME sample=%u wall=%ld.%09ld mono=%ld.%09ld\n",sample,
                       (long)wall.tv_sec,wall.tv_nsec,(long)mono.tv_sec,mono.tv_nsec);
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
        if (thread_activity(number,sample,argc==3)) return 1;
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
