// Amerika OS dock: floating, centred, and never hidden.
var dock = new Panel
dock.location = "bottom"
dock.height = 2 * Math.ceil(gridUnit * 3.4 / 2)
dock.floating = true
dock.hiding = "none"
dock.alignment = "center"
dock.lengthMode = "fit"

var tasks = dock.addWidget("org.kde.plasma.icontasks")
tasks.currentConfigGroup = ["General"]
tasks.writeConfig("launchers", [
    "applications:amerika-social.desktop",
    "applications:amerika-ai.desktop",
    "applications:amerika-venture.desktop",
    "applications:amerika-files.desktop",
    "applications:amerika-terminal.desktop",
    "applications:amerika-software.desktop"
])
tasks.writeConfig("iconSpacing", 2)
