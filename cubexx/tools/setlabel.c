/* Set the SELinux label of a file so the Android shell domain can read it.
 * Run by the debug init before switch_root (kernel context, pre policy load).
 * Usage: setlabel <path> [context]   default context: shell_data_file */
#include <sys/xattr.h>
#include <string.h>

int main(int argc, char **argv)
{
    if (argc < 2)
        return 2;
    const char *ctx = (argc >= 3) ? argv[2] : "u:object_r:shell_data_file:s0";
    if (setxattr(argv[1], "security.selinux", ctx, strlen(ctx) + 1, 0) != 0)
        return 1;
    return 0;
}