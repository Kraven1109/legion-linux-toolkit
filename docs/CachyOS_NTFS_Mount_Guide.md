# CachyOS NTFS Mount & Dual-Boot Reference Guide

Quick reference for mounting secondary NTFS NVMe drives (`Data1` and `Data2`) on **CachyOS** (Kernel 7.2+) alongside **Windows 11**.

---

## 1. Active `/etc/fstab` Configuration

```text
# Data1 (nvme0n1p4)
UUID=8C44A73144A71D48  /DATA1  ntfs  uid=1000,gid=1000,dmask=0022,fmask=0022,iocharset=utf8,windows_names,nofail  0  0

# Data2 (nvme1n1p1)
UUID=7824CEC324CE841A  /DATA2  ntfs  uid=1000,gid=1000,dmask=0022,fmask=0022,iocharset=utf8,windows_names,nofail  0  0
```

---

## 2. Mount Options Breakdown

| Option | Purpose |
| :--- | :--- |
| **`ntfs`** | Uses the modern **in-kernel NTFS driver** (introduced in Linux 7.1+ by Namjae Jeon, built on `folio`/`iomap`). Native NVMe speed without FUSE CPU overhead. |
| **`uid=1000,gid=1000`** | Assigns ownership to user `quangtm`. |
| **`dmask=0022,fmask=0022`** | Sets permissions to `0755` (`rwxr-xr-x`) for directories and files, enabling direct script/binary execution (e.g., `./llm.sh`). |
| **`iocharset=utf8`** | Ensures correct UTF-8 character encoding for filenames. |
| **`windows_names`** | Blocks Linux from creating files with illegal Windows characters (`:`, `*`, `?`, `"`, `<`, `>`, `|`, trailing spaces/dots). Protects MFT directory indexes from being flagged as corrupt by Windows `chkdsk`. |
| **`nofail`** | Prevents boot halts if a partition is busy or undergoing check. |
| **`0 0`** | Disables dump and fsck passes (NTFS does not use standard Linux ext fsck). |

### Dangerous Options to AVOID:
* **`force`**: Never keep this permanently in `fstab`. It forces mounting over dirty/uncommitted transaction journals, causing gradual silent MFT corruption over time.
* **`lazytime`**: Keeps timestamp metadata only in RAM; causes metadata desync and dirty-bit flags upon rebooting into Windows.

---

## 3. Package Management & Driver Architecture

* **In-Kernel Driver (`ntfs.ko`)**: Self-contained in the Linux kernel (`/lib/modules/.../kernel/fs/ntfs/ntfs.ko.zst`).
* **`ntfs-3g` Package**: **Uninstalled** so that `/usr/bin/mount.ntfs` does not hijack `mount` calls to user-space FUSE.
* **`ntfsprogs` Package**: **Kept installed** to provide standalone offline utilities (`/usr/bin/ntfsfix`, `mkntfs`).

---

## 4. Quick Troubleshooting & Maintenance

### Check Active Mounts
```bash
findmnt /DATA1
findmnt /DATA2
```
*(Verify `FSTYPE` is `ntfs`, not `fuseblk`)*.

### Reload `/etc/fstab` without rebooting
```bash
sudo systemctl daemon-reload
sudo mount -a
```

### If a Drive is Flagged Dirty (`volume is dirty`)

**Option A: Linux Quick Clear (`ntfsfix`)**
```bash
sudo ntfsfix -d /dev/nvme1n1p1   # For DATA2
sudo ntfsfix -d /dev/nvme0n1p4   # For DATA1
sudo mount -a
```

**Option B: Official Microsoft Repair (Windows 11 USB Installer)**
1. Boot Windows 11 installation USB.
2. At first screen, press Shift + F10.
3. Find drive letter with `diskpart` -> `list volume`.
4. Run:
   ```cmd
   chkdsk E: /f /x
   wpeutil shutdown
   ```

### Windows 11 Prevention (One-time)
Run in Administrator Command Prompt on Windows:
```cmd
powercfg /h off
```
*(Completely removes `hiberfil.sys` and eliminates Fast Startup locks).*

---

## 5. Router SMB / CIFS Network Mounts (`lulu_home`)

Network shares hosted on router (`192.168.1.1`) mounted locally without needing `sudo`.

### `/etc/fstab` Entries
```text
//192.168.1.1/G  /home/quangtm/lulu_home/G  cifs  username=media,password=123lulu,vers=2.0,uid=1000,gid=1000,noauto,user,_netdev,iocharset=utf8  0  0
//192.168.1.1/H  /home/quangtm/lulu_home/H  cifs  username=media,password=123lulu,vers=2.0,uid=1000,gid=1000,noauto,user,_netdev,iocharset=utf8  0  0
```

### Usage (No sudo required):
* **Mount both:**
  ```bash
  mount ~/lulu_home/G && mount ~/lulu_home/H
  ```
* **Unmount both:**
  ```bash
  umount ~/lulu_home/G ~/lulu_home/H
  ```
* **Note on `vers=2.0`:** The router's Samba daemon runs dialect `SMB2_02`, so `vers=2.0` is required.
