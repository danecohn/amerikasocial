import QtQuick 2.15
import QtQuick.Controls 2.15
import Qt5Compat.GraphicalEffects

// Amerika OS login screen (SDDM greeter theme). Retro-futurist: horizon wallpaper, neon cartridge avatar, chrome glass card.
Item {
    id: root
    width: 1600
    height: 900

    readonly property color accent: config.accent ? config.accent : "#ff2e63"
    readonly property color second: config.secondary ? config.secondary : "#19e3ff"
    property bool busy: false
    property string message: ""

    function currentUser() { return users.currentItem ? users.currentItem.userName : userModel.lastUser }

    function attemptLogin() {
        if (busy || password.text.length === 0) return
        message = ""
        busy = true
        sddm.login(currentUser(), password.text, session.index)
    }

    // ------------------------------------------------------------------ background
    Image {
        id: wallpaper
        anchors.fill: parent
        source: config.background ? config.background : "assets/horizon.png"
        fillMode: Image.PreserveAspectCrop
        smooth: true
    }
    Rectangle {  // a soft darkening so the card reads
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#99070610" }
            GradientStop { position: 0.55; color: "#33070610" }
            GradientStop { position: 1.0; color: "#cc070610" }
        }
    }
    RadialGradient {  // pulsing glow where the sun sits
        id: halo
        width: parent.width * 0.9; height: parent.height * 0.9
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.62 - height * 0.5
        horizontalRadius: width * 0.5; verticalRadius: height * 0.5
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.38) }
            GradientStop { position: 0.55; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.0) }
            GradientStop { position: 1.0; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.0) }
        }
        SequentialAnimation on opacity {
            loops: Animation.Infinite
            NumberAnimation { from: 0.55; to: 1.0; duration: 3200; easing.type: Easing.InOutSine }
            NumberAnimation { from: 1.0; to: 0.55; duration: 3200; easing.type: Easing.InOutSine }
        }
    }
    Rectangle {  // CRT scanlines, very light
        anchors.fill: parent
        opacity: 0.05
        gradient: Gradient { GradientStop { position: 0; color: "white" } GradientStop { position: 1; color: "transparent" } }
        visible: false
    }

    // ------------------------------------------------------------------ brand
    Row {
        id: brand
        x: 40; y: 34
        spacing: 14
        Image { source: "assets/logo.svg"; width: 46; height: 46; sourceSize.width: 92; sourceSize.height: 92 }
        Column {
            anchors.verticalCenter: parent.verticalCenter
            Text { text: "AMERIKA OS"; color: "#f2f0fa"; font.family: "Inter"; font.pixelSize: 22; font.weight: Font.ExtraBold; font.letterSpacing: 5 }
            Text { text: "RETRO-FUTURE · 3.0"; color: root.second; font.family: "JetBrains Mono"; font.pixelSize: 11; font.letterSpacing: 3 }
        }
    }

    // ------------------------------------------------------------------ clock
    Column {
        id: clockBox
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.07
        spacing: 2
        Text {
            id: time
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatTime(new Date(), "hh:mm")
            color: "#ffffff"
            font.family: "JetBrains Mono"; font.pixelSize: Math.max(72, root.height * 0.11); font.weight: Font.Light; font.letterSpacing: 6
            layer.enabled: true
            layer.effect: Glow { radius: 12; samples: 25; color: root.second; spread: 0.1; transparentBorder: true }
        }
        Text {
            id: date
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatDate(new Date(), "dddd · d MMMM").toUpperCase()
            color: "#c9c6dc"
            font.family: "Inter"; font.pixelSize: 16; font.letterSpacing: 6; font.weight: Font.DemiBold
        }
    }
    Timer {
        interval: 1000; running: true; repeat: true
        onTriggered: { time.text = Qt.formatTime(new Date(), "hh:mm"); date.text = Qt.formatDate(new Date(), "dddd · d MMMM").toUpperCase() }
    }

    // ------------------------------------------------------------------ the login card
    Rectangle {
        id: card
        width: 460; height: 430
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.34
        radius: 30
        color: "#d90f0e18"
        border.width: 1; border.color: "#44ffffff"
        layer.enabled: true
        layer.effect: DropShadow { horizontalOffset: 0; verticalOffset: 18; radius: 48; samples: 49; color: "#cc000000" }

        Rectangle { // chrome rim highlight along the top edge
            anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 28; rightMargin: 28 }
            height: 2; radius: 1
            gradient: Gradient { orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: root.accent }
                GradientStop { position: 1.0; color: "transparent" } }
        }

        // ---- who
        ListView {
            id: users
            anchors { top: parent.top; topMargin: 34; horizontalCenter: parent.horizontalCenter }
            width: parent.width - 120; height: 176
            orientation: ListView.Horizontal
            snapMode: ListView.SnapOneItem
            highlightRangeMode: ListView.StrictlyEnforceRange
            highlightMoveDuration: 260
            interactive: false
            clip: true
            model: userModel
            currentIndex: userModel.lastIndex >= 0 ? userModel.lastIndex : 0
            delegate: Item {
                property string userName: model.name
                width: users.width; height: users.height
                Column {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 10
                    Item {
                        id: avatar
                        width: 112; height: 112
                        anchors.horizontalCenter: parent.horizontalCenter
                        Rectangle {
                            id: tile
                            anchors.fill: parent; radius: 30
                            gradient: Gradient { GradientStop { position: 0; color: "#2f2d48" } GradientStop { position: 1; color: "#10101c" } }
                            border.width: 3; border.color: "#d8d8ee"
                            layer.enabled: true
                            layer.effect: Glow { radius: 14; samples: 29; color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.7); spread: 0.15 }
                        }
                        Image {
                            id: face
                            anchors.fill: parent; anchors.margins: 4
                            source: model.icon ? model.icon : ""
                            fillMode: Image.PreserveAspectCrop
                            visible: false
                        }
                        Rectangle { id: faceMask; anchors.fill: face; radius: 26; visible: false }
                        OpacityMask { anchors.fill: face; source: face; maskSource: faceMask; visible: face.status === Image.Ready }
                        Text {
                            anchors.centerIn: parent
                            visible: face.status !== Image.Ready
                            text: (model.realName ? model.realName : model.name).charAt(0).toUpperCase()
                            color: "#ffffff"; font.family: "Inter"; font.pixelSize: 54; font.weight: Font.ExtraBold
                            layer.enabled: true
                            layer.effect: Glow { radius: 10; samples: 21; color: root.accent; spread: 0.2; transparentBorder: true }
                        }
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: model.realName ? model.realName : model.name
                        color: "#f2f0fa"; font.family: "Inter"; font.pixelSize: 21; font.weight: Font.Bold
                    }
                }
            }
        }
        Repeater {  // previous / next user, only when there is more than one
            model: userModel.count > 1 ? 2 : 0
            delegate: Rectangle {
                width: 36; height: 36; radius: 18
                x: index === 0 ? 22 : parent.width - 22 - width
                y: 34 + 56
                color: "#26ffffff"; border.color: "#44ffffff"
                Text { anchors.centerIn: parent; text: index === 0 ? "‹" : "›"; color: "white"; font.pixelSize: 24 }
                MouseArea { anchors.fill: parent; onClicked: index === 0 ? users.decrementCurrentIndex() : users.incrementCurrentIndex() }
            }
        }

        // ---- password
        Rectangle {
            id: field
            anchors { top: users.bottom; topMargin: 14; horizontalCenter: parent.horizontalCenter }
            width: parent.width - 80; height: 52; radius: 16
            color: "#99000000"
            border.width: password.activeFocus ? 2 : 1
            border.color: root.message.length > 0 ? "#ff5d6e" : (password.activeFocus ? root.second : "#55ffffff")
            Behavior on border.color { ColorAnimation { duration: 150 } }
            layer.enabled: password.activeFocus
            layer.effect: Glow { radius: 10; samples: 21; color: Qt.rgba(root.second.r, root.second.g, root.second.b, 0.55); spread: 0.1 }
            TextField {
                id: password
                anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 56
                echoMode: TextInput.Password
                passwordCharacter: "•"
                placeholderText: "Password"
                placeholderTextColor: "#8a87a3"
                color: "#ffffff"; selectionColor: root.accent
                font.family: "Inter"; font.pixelSize: 18
                background: Item {}
                enabled: !root.busy
                focus: true
                Keys.onReturnPressed: root.attemptLogin()
                Keys.onEnterPressed: root.attemptLogin()
                Keys.onEscapePressed: text = ""
            }
            Rectangle {  // the go button
                anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                width: 40; height: 36; radius: 12
                gradient: Gradient { GradientStop { position: 0; color: root.accent } GradientStop { position: 1; color: Qt.darker(root.accent, 1.8) } }
                border.width: 1; border.color: "#66ffffff"
                opacity: password.text.length > 0 && !root.busy ? 1.0 : 0.45
                Behavior on opacity { NumberAnimation { duration: 120 } }
                Text { anchors.centerIn: parent; text: "→"; color: "white"; font.pixelSize: 22; font.weight: Font.Bold }
                MouseArea { anchors.fill: parent; onClicked: root.attemptLogin() }
            }
        }
        Text {
            id: feedback
            anchors { top: field.bottom; topMargin: 12; horizontalCenter: parent.horizontalCenter }
            text: root.busy ? "SIGNING IN…" : root.message
            color: root.busy ? root.second : "#ff7a88"
            font.family: "JetBrains Mono"; font.pixelSize: 12; font.letterSpacing: 3
        }

        // ---- session
        Rectangle {
            id: sessionPill
            anchors { bottom: parent.bottom; bottomMargin: 26; horizontalCenter: parent.horizontalCenter }
            height: 34; width: sessionText.width + 40; radius: 17
            color: "#22ffffff"; border.width: 1; border.color: "#44ffffff"
            Text {
                id: sessionText
                anchors.centerIn: parent
                text: "SESSION · " + session.name.toUpperCase() + (sessionModel.count > 1 ? "  ▸" : "")
                color: "#dcd9ee"; font.family: "JetBrains Mono"; font.pixelSize: 11; font.letterSpacing: 2
            }
            MouseArea { anchors.fill: parent; enabled: sessionModel.count > 1; onClicked: session.next() }
        }
    }

    // session state (cycled by clicking the pill)
    QtObject {
        id: session
        property int index: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0
        property string name: ""
        function refresh() {
            var i = sessionModel.index(index, 0)
            name = sessionModel.data(i, Qt.UserRole + 4) || sessionModel.data(i, Qt.DisplayRole) || "Amerika OS"
        }
        function next() { index = (index + 1) % Math.max(1, sessionModel.count); refresh() }
        Component.onCompleted: {
            // prefer Amerika OS the first time, when there is no remembered choice
            for (var i = 0; i < sessionModel.count; i++) {
                var n = sessionModel.data(sessionModel.index(i, 0), Qt.UserRole + 4) || ""
                if (sessionModel.lastIndex < 0 && String(n).indexOf("Amerika OS") === 0) { index = i; break }
            }
            refresh()
        }
    }

    // ------------------------------------------------------------------ power
    Row {
        anchors { right: parent.right; bottom: parent.bottom; rightMargin: 40; bottomMargin: 34 }
        spacing: 14
        Repeater {
            model: [
                { icon: "assets/sleep.svg", tip: "Sleep", ok: sddm.canSuspend, act: function () { sddm.suspend() } },
                { icon: "assets/restart.svg", tip: "Restart", ok: sddm.canReboot, act: function () { sddm.reboot() } },
                { icon: "assets/power.svg", tip: "Shut down", ok: sddm.canPowerOff, act: function () { sddm.powerOff() } }
            ]
            delegate: Rectangle {
                visible: modelData.ok
                width: 48; height: 48; radius: 16
                color: hover.containsMouse ? "#33ffffff" : "#1fffffff"
                border.width: 1; border.color: hover.containsMouse ? root.accent : "#44ffffff"
                Image { anchors.centerIn: parent; source: modelData.icon; width: 22; height: 22; sourceSize.width: 44; sourceSize.height: 44 }
                MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; onClicked: modelData.act() }
                ToolTip.visible: hover.containsMouse; ToolTip.text: modelData.tip
            }
        }
    }
    Text {
        anchors { left: parent.left; bottom: parent.bottom; leftMargin: 40; bottomMargin: 42 }
        text: sddm.hostName ? sddm.hostName.toUpperCase() : ""
        color: "#9a98b0"; font.family: "JetBrains Mono"; font.pixelSize: 11; font.letterSpacing: 3
    }

    // ------------------------------------------------------------------ results of a login attempt
    SequentialAnimation {
        id: shake
        PropertyAnimation { target: card; property: "anchors.horizontalCenterOffset"; to: -16; duration: 55 }
        PropertyAnimation { target: card; property: "anchors.horizontalCenterOffset"; to: 16; duration: 80 }
        PropertyAnimation { target: card; property: "anchors.horizontalCenterOffset"; to: -10; duration: 70 }
        PropertyAnimation { target: card; property: "anchors.horizontalCenterOffset"; to: 0; duration: 60 }
    }
    Connections {
        target: sddm
        function onLoginFailed() {
            root.busy = false
            root.message = "WRONG PASSWORD"
            password.text = ""
            password.forceActiveFocus()
            shake.restart()
        }
        function onLoginSucceeded() { handoff.start() }
    }

    // ------------------------------------------------------------------ hand-off to the session (the startup screen takes over)
    Rectangle {
        id: fade
        anchors.fill: parent
        color: "#05040a"
        opacity: 0
        visible: opacity > 0
        Column {
            anchors.centerIn: parent
            spacing: 18
            Image { anchors.horizontalCenter: parent.horizontalCenter; source: "assets/logo.svg"; width: 120; height: 120; sourceSize.width: 240; sourceSize.height: 240 }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "STARTING AMERIKA OS"; color: "#f2f0fa"; font.family: "Inter"; font.pixelSize: 18; font.weight: Font.Bold; font.letterSpacing: 8 }
        }
    }
    NumberAnimation { id: handoff; target: fade; property: "opacity"; from: 0; to: 1; duration: 450; easing.type: Easing.InOutQuad }

    // ------------------------------------------------------------------ development hook: save a screenshot and quit
    Timer {
        interval: 2600
        running: config.screenshot !== undefined && String(config.screenshot).length > 0
        onTriggered: root.grabToImage(function (result) { result.saveToFile(config.screenshot); Qt.quit() })
    }

    Component.onCompleted: password.forceActiveFocus()
}
