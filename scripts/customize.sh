#!/bin/bash
set -euo pipefail
test -f /usr/share/lynux/.building || { echo 'This script only runs inside a staged image.' >&2; exit 1; }
locale-gen
cat /usr/share/lynux/os-release > /etc/os-release
ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
id live >/dev/null 2>&1 || useradd --create-home --groups wheel,audio,video,input --shell /bin/bash live
passwd -d live
passwd -l root
chmod 0440 /etc/sudoers.d/lynux-live
visudo -cf /etc/sudoers.d/lynux-live
python - <<'PY'
import configparser
from pathlib import Path
profile = configparser.ConfigParser()
profile.read('/etc/skel/.config/fcitx5/profile')
for section in profile.sections():
    if '/Items/' in section:
        name = profile[section]['name']
        if not name.startswith('keyboard-') and not Path(f'/usr/share/fcitx5/inputmethod/{name}.conf').is_file():
            raise ValueError(f'Configured input method is unavailable: {name}')
PY
mkdir -p /workspace /root/.config /root/.local/share /root/.local/state
chmod 0700 /root
systemctl enable NetworkManager systemd-timesyncd sddm lynux-state lynux-keyring lynux-boot-report
systemctl disable sshd.service systemd-networkd.service systemd-resolved.service 2>/dev/null || true
# Do not activate host swap partitions, even if an operator later opens a disk.
systemctl mask swap.target
# arch-chroot bind-mounts resolv.conf; NetworkManager writes it after the live system boots.
python /usr/local/lib/lynux/install-harnesses.py /usr/share/lynux/lock
# Precompile Rime data for offline first use; deployment writes only into the live user's home.
if command -v rime_deployer >/dev/null; then
    runuser -u live -- rime_deployer --build /home/live/.local/share/fcitx5/rime /usr/share/rime-data /home/live/.local/share/fcitx5/rime/build
fi
chown -R live:live /home/live
cc -O2 -Wall -Wextra -Werror /usr/local/lib/lynux/ventoy-find.c -o /usr/bin/lynux-ventoy-find
if [[ -f /usr/share/lynux/linux-aarch64.preset ]]; then
    # Preserve the kernel package's exact ALL_kver, overriding only live output names.
    test -s /etc/mkinitcpio.d/linux-aarch64.preset
    printf '\n# Lynux Live ISO overrides\n' >> /etc/mkinitcpio.d/linux-aarch64.preset
    cat /usr/share/lynux/linux-aarch64.preset >> /etc/mkinitcpio.d/linux-aarch64.preset
    cp /boot/Image /boot/vmlinuz-linux-aarch64
fi
mkinitcpio -P
if [[ -f /usr/share/lynux/linux-aarch64.preset ]]; then
    test -s /boot/initramfs-linux-aarch64.img
    rm -f /boot/initramfs-linux.img /boot/initramfs-linux-fallback.img
fi
pacman -Q > /usr/share/lynux/packages.txt
node --version > /usr/share/lynux/node-version.txt
python --version > /usr/share/lynux/python-version.txt
python - <<'PY'
import json, shutil
from pathlib import Path
for tool in json.loads(Path('/usr/share/lynux/harnesses.json').read_text())['harnesses'].values():
    for item in tool['state']:
        path = Path(item['path'])
        if not path.is_relative_to('/root'):
            raise ValueError('Unexpected state path in image cleanup')
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
PY
rm -rf /root/.npm /root/.cache /var/cache/lynux
rm -f /root/.bash_history
rm -f /usr/share/lynux/.building
