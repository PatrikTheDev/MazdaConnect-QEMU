/* Minimal registry/sync probe. Wire format: wayland.freedesktop.org/docs/book/Protocol.html */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

static int receive(int fd, void *buffer, size_t count) {
    unsigned char *p = buffer;
    while (count) {
        ssize_t n = read(fd, p, count);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        p += n;
        count -= n;
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    alarm(5);
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    if (strlen(argv[1]) >= sizeof(address.sun_path)) return 2;
    strcpy(address.sun_path, argv[1]);
    if (connect(fd, (struct sockaddr *)&address, sizeof(address))) { perror("connect"); return 1; }
    /* wl_display.get_registry(new_id=2), then wl_display.sync(new_id=3). */
    uint32_t requests[] = {1, (12u << 16) | 1u, 2, 1, 12u << 16, 3};
    if (write(fd, requests, sizeof(requests)) != sizeof(requests)) return 1;
    int compositor = 0, shm = 0, ivi = 0, outputs = 0;
    for (;;) {
        uint32_t header[2], payload[4096];
        if (receive(fd, header, sizeof(header))) return 1;
        unsigned size = header[1] >> 16, opcode = header[1] & 65535;
        if (size < 8 || size % 4 || size - 8 > sizeof(payload)) return 1;
        if (receive(fd, payload, size - 8)) return 1;
        if (header[0] == 1 && opcode == 0) { fputs("Wayland protocol error\n", stderr); return 1; }
        if (header[0] == 2 && opcode == 0) {
            if (size < 20) return 1;
            unsigned length = payload[1];
            if (!length || length > size - 20) return 1;
            unsigned padded = (length + 3) & ~3u;
            if (20 + padded != size) return 1;
            char *name = (char *)&payload[2];
            if (name[length - 1] != 0) return 1;
            printf("GLOBAL %s version=%u\n", name, payload[2 + padded / 4]);
            compositor |= !strcmp(name, "wl_compositor");
            shm |= !strcmp(name, "wl_shm");
            ivi |= strstr(name, "ivi") != NULL;
            outputs += !strcmp(name, "wl_output");
        }
        if (header[0] == 3 && opcode == 0 && size == 12) break;
    }
    close(fd);
    if (!compositor || !shm || !ivi) return 1;
    printf("WAYLAND_ROUNDTRIP_OK outputs=%d\n", outputs);
    return 0;
}
