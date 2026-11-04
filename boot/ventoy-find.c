/* Resolve Ventoy's checksummed EFI handoff without evaluating any filename as shell code. */
#define _GNU_SOURCE
#include <dirent.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int read_bytes(const char *path, void *data, size_t size) {
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    int ok = fread(data, 1, size, f) == size;
    fclose(f);
    return ok;
}

static char *join(const char *a, const char *b, const char *c) {
    char *result = NULL;
    if (asprintf(&result, "%s/%s%s", a, b, c) < 0) exit(2);
    return result;
}

int main(int argc, char **argv) {
    const char *param = "/sys/firmware/efi/efivars/VentoyOsParam-77772020-2e77-6576-6e74-6f792e6e6574";
    const char *sys = "/sys/class/block", *dev = "/dev";
    /* Alternate roots allow tests against synthetic, non-device fixtures. */
    if (argc == 4) { param = argv[1]; sys = argv[2]; dev = argv[3]; }
    else if (argc != 1) return 2;
    uint8_t record[516], sector[512];
    const uint8_t magic[16] = {0x20,0x20,0x77,0x77,0x77,0x2e,0x76,0x65,0x6e,0x74,0x6f,0x79,0x2e,0x6e,0x65,0x74};
    if (!read_bytes(param, record, sizeof(record))) return 1;
    uint8_t *data = record + 4;
    unsigned sum = 0;
    for (unsigned i = 0; i < 512; i++) sum += data[i];
    if (memcmp(data, magic, 16) || (sum & 255)) return 1;
    unsigned partition = data[41] | ((unsigned)data[42] << 8);
    char *image = (char *)data + 45;
    size_t length = strnlen(image, 384);
    if (!partition || !length || length == 384 || image[0] != '/') return 1;
    for (size_t i = 0; i < length; i++) if ((unsigned char)image[i] < 32 || image[i] == 127) return 1;
    if (strstr(image, "/../") || (length >= 3 && !strcmp(image + length - 3, "/.."))) return 1;
    DIR *disks = opendir(sys);
    if (!disks) return 1;
    struct dirent *disk;
    while ((disk = readdir(disks))) {
        if (disk->d_name[0] == '.') continue;
        char *ispart = join(sys, disk->d_name, "/partition");
        FILE *partfile = fopen(ispart, "r");
        free(ispart);
        if (partfile) { fclose(partfile); continue; }
        char *device = join(dev, disk->d_name, "");
        int matched = read_bytes(device, sector, sizeof(sector)) && !memcmp(sector + 384, data + 17, 16);
        free(device);
        if (!matched) continue;
        char *diskdir = join(sys, disk->d_name, "");
        DIR *parts = opendir(diskdir);
        if (!parts) { free(diskdir); continue; }
        struct dirent *part;
        while ((part = readdir(parts))) {
            if (part->d_name[0] == '.') continue;
            char *numberfile = join(diskdir, part->d_name, "/partition");
            FILE *number = fopen(numberfile, "r");
            free(numberfile);
            unsigned value = 0;
            int ok = number && fscanf(number, "%u", &value) == 1 && value == partition;
            if (number) fclose(number);
            if (ok) {
                printf("%s/%s\n%s\n", dev, part->d_name, image);
                closedir(parts); free(diskdir); closedir(disks);
                return 0;
            }
        }
        closedir(parts); free(diskdir);
    }
    closedir(disks);
    return 1;
}
