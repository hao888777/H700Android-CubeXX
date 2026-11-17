// Minimal force-feedback rumble tester for CubeXX ANBERNIC-keys.
// Uploads a FF_RUMBLE effect, plays it for N ms, stops. Read/write on the
// input event node only; no persistent change. Used to confirm whether a
// physical rumble motor is wired to the input FF path.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/input.h>

static int play(int fd, int id, int value) {
    struct input_event ev;
    memset(&ev, 0, sizeof(ev));
    ev.type = EV_FF;
    ev.code = id;
    ev.value = value;
    if (write(fd, &ev, sizeof(ev)) != sizeof(ev)) {
        fprintf(stderr, "write EV_FF value=%d failed: %s\n", value, strerror(errno));
        return -1;
    }
    memset(&ev, 0, sizeof(ev));
    ev.type = EV_SYN;
    ev.code = SYN_REPORT;
    ev.value = 0;
    write(fd, &ev, sizeof(ev));
    return 0;
}

int main(int argc, char **argv) {
    const char *dev = argc > 1 ? argv[1] : "/dev/input/event1";
    int ms = argc > 2 ? atoi(argv[2]) : 3000;
    if (ms < 100) ms = 100;
    if (ms > 10000) ms = 10000;

    int fd = open(dev, O_RDWR);
    if (fd < 0) {
        fprintf(stderr, "open %s O_RDWR failed: %s\n", dev, strerror(errno));
        fprintf(stderr, "(EACCES => SELinux/perm blocks shell writing input node)\n");
        return 2;
    }

    char name[256] = {0};
    ioctl(fd, EVIOCGNAME(sizeof(name)), name);
    printf("device: %s = \"%s\"\n", dev, name);

    unsigned long ffbit[FF_MAX / (8 * sizeof(long)) + 1] = {0};
    if (ioctl(fd, EVIOCGBIT(EV_FF, sizeof(ffbit)), ffbit) < 0) {
        fprintf(stderr, "EVIOCGBIT(EV_FF) failed: %s\n", strerror(errno));
        close(fd);
        return 3;
    }
    int has_rumble = (ffbit[FF_RUMBLE / (8 * sizeof(long))] >> (FF_RUMBLE % (8 * sizeof(long)))) & 1;
    int has_periodic = (ffbit[FF_PERIODIC / (8 * sizeof(long))] >> (FF_PERIODIC % (8 * sizeof(long)))) & 1;
    printf("FF_RUMBLE=%d FF_PERIODIC=%d\n", has_rumble, has_periodic);

    struct ff_effect eff;
    memset(&eff, 0, sizeof(eff));
    eff.id = -1;
    eff.replay.length = ms;
    eff.replay.delay = 0;
    if (has_rumble) {
        eff.type = FF_RUMBLE;
        eff.u.rumble.strong_magnitude = 0xFFFF;
        eff.u.rumble.weak_magnitude = 0xFFFF;
    } else if (has_periodic) {
        eff.type = FF_PERIODIC;
        eff.u.periodic.waveform = FF_SQUARE;
        eff.u.periodic.period = 100;
        eff.u.periodic.magnitude = 0x7FFF;
        eff.u.periodic.offset = 0;
        eff.u.periodic.phase = 0;
    } else {
        fprintf(stderr, "no FF_RUMBLE/FF_PERIODIC capability\n");
        close(fd);
        return 4;
    }

    if (ioctl(fd, EVIOCSFF, &eff) < 0) {
        fprintf(stderr, "EVIOCSFF (type=%d) failed: %s\n", eff.type, strerror(errno));
        close(fd);
        return 5;
    }
    printf("uploaded effect id=%d type=%d, playing %d ms ...\n", eff.id, eff.type, ms);
    fflush(stdout);

    if (play(fd, eff.id, 1) < 0) { close(fd); return 6; }
    usleep(ms * 1000);
    play(fd, eff.id, 0);
    ioctl(fd, EVIOCRMFF, eff.id);
    printf("done. Did the device physically vibrate? (yes/no)\n");
    close(fd);
    return 0;
}