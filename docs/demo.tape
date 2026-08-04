Output assets/demo.gif
Require installed dropprobe
Set FontSize 14
Set Width 1200
Set Height 640
Set Theme {"background": "#1D1D1F", "foreground": "#F5F5F7", "name": "DropProbe"}
Set Padding 20

# 10-minute happy path: clone → install → first visible result.
# The real binary drives the tape (pip install -e . runs in demo.yml).
Type "dropprobe latest --list"
Sleep 400ms
Enter
Sleep 4s

# show the version + help surface too
Type "dropprobe --version"
Sleep 300ms
Enter
Sleep 1s

Type "dropprobe latest --help"
Sleep 300ms
Enter
Sleep 2s
