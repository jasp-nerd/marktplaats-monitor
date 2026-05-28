# demo.tape — terminal demo for the README.
#
# Regenerate with:  vhs assets/demo.tape
# Tooling:          https://github.com/charmbracelet/vhs  (brew install vhs)
# Output:           assets/demo.gif
#
# Run from the repo root so the relative paths resolve.

Output assets/demo.gif

Set Shell "bash"
Set FontSize 15
Set Width 1200
Set Height 720
Set Theme "Catppuccin Mocha"
Set TypingSpeed 25ms
Set PlaybackSpeed 1.2
Set Padding 30

# Hidden setup: activate venv (so `python -m marktplaats_monitor` resolves)
# and seed a throwaway demo DB so the `stats` frame renders a populated table.
Hide
Type "[ -f .venv/bin/activate ] && source .venv/bin/activate"
Enter
Type "python assets/seed-demo.py"
Enter
Type "clear"
Enter
Show

# 1. The CLI surface
Type "python -m marktplaats_monitor --help"
Enter
Sleep 3.5s
Type "clear"
Enter

# 2. A glance at the annotated config (defaults block + first search)
Type "head -62 config.example.yaml"
Enter
Sleep 5s
Type "clear"
Enter

# 3. Stats command against the seeded demo DB
Type "python -m marktplaats_monitor --db /tmp/mp-demo.sqlite3 stats"
Enter
Sleep 4s
