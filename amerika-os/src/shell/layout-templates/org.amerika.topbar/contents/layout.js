// Amerika OS top bar: Amerika menu, global menu, tray and clock. Always visible.
var bar = new Panel
bar.location = "top"
bar.height = 2 * Math.ceil(gridUnit * 1.7 / 2)
bar.floating = false
bar.hiding = "none"

var menu = bar.addWidget("org.kde.plasma.kickoff")
menu.currentConfigGroup = ["General"]
menu.writeConfig("icon", "amerika-hub")
menu.writeConfig("favorites", [
    "applications:amerika-social.desktop",
    "applications:amerika-ai.desktop",
    "applications:amerika-venture.desktop",
    "applications:amerika-files.desktop",
    "applications:amerika-terminal.desktop",
    "applications:amerika-office.desktop",
    "applications:amerika-software.desktop",
    "applications:amerika-hub.desktop"
])

bar.addWidget("org.kde.plasma.appmenu")
bar.addWidget("org.kde.plasma.panelspacer")
bar.addWidget("org.kde.plasma.marginsseparator")
bar.addWidget("org.kde.plasma.systemtray")
bar.addWidget("org.kde.plasma.digitalclock")
