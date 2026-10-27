import QtQuick 2.15
import "Config.js" as Config

Rectangle {
    id: root
    objectName: "babblet"
    width: 1404
    height: 1872
    anchors.fill: parent
    color: "white"
    signal close()
    property string serverUrl: Config.serverUrl
    property string token: Config.token
    property bool running: true
    property bool online: false
    property bool busy: false
    property bool clean: true
    property bool showSpoken: true
    onShowSpokenChanged: rebuildColumns()
    property string readerLayout: "off"
    property var readerCodes: []
    property var readerAngles: []
    property int readerTarget: -1
    onReaderLayoutChanged: { readerAngles = []; rebuildColumns() }
    property bool settings: false
    property bool speechMode: false
    property bool landscape: false
    property bool syncWithDisplay: true
    property string searchText: ""
    readonly property real pageWidth: landscape ? root.height : root.width
    readonly property real pageHeight: landscape ? root.width : root.height
    readonly property int workRow: {
        var pending = snapshot.pending_activity || {};
        if (pending.active) return (pending.display_index - 1) % slotCount;
        var rows = snapshot.slots || [];
        var active = snapshot.translation_activity;
        for (var i = 0; i < rows.length; i++) {
            if (rows[i] && active && rows[i].utterance_id === active.utterance_id) return i;
        }
        return -1;
    }
    readonly property bool workVisible: workRow >= 0
    readonly property string workLabel: snapshot.pending_activity && snapshot.pending_activity.active ? snapshot.pending_activity.label : "Translating…"
    readonly property int workLevel: workLabel.indexOf("Listening") >= 0 ? 1 : workLabel.indexOf("Transcribing") >= 0 ? 2 : workLabel.indexOf("Translating") >= 0 ? 4 : 3
    property string connectionMessage: "Connecting to computer…"
    property string settingsError: ""
    property string lastSignature: ""
    property var request: null
    property var snapshot: ({})
    property var columns: []
    property var catalog: []
    property var speechCatalog: []
    property var selected: []
    property var expected: []
    property var flipped: ({})
    property int slotCount: 6
    property int successfulPolls: 0
    property int changedCells: 0
    readonly property int latestRow: {
        var rows = snapshot.slots || []
        var latest = -1, newest = -1
        for (var i = 0; i < rows.length; i++) {
            if (rows[i] && rows[i].display_index > newest) { newest = rows[i].display_index; latest = i }
        }
        return latest
    }
    readonly property int nextReplaceRow: {
        if (latestRow < 0 || slotCount < 2) return -1
        var next = (latestRow + 1) % slotCount
        return (snapshot.slots || [])[next] ? next : -1
    }
    readonly property var languageOptions: (speechMode ? speechCatalog : catalog).filter(function(item) { return (readerTarget < 0 || selected.indexOf(item.code) >= 0) && (item.name + " " + item.native + " " + item.code).toLowerCase().indexOf(searchText.toLowerCase()) >= 0 })
    FontLoader { id: serifFont; source: "../fonts/NotoSerif.ttf" }
    FontLoader { id: latinFont; source: "../fonts/NotoSans.ttf" }
    Fonts { id: scriptFonts }
    function fontFor(code) { return scriptFonts.familyFor(code) }
    function nativeCaption(language) { return language.native }

    // AppLoad owns the window. Stop network requests when it unloads the QML.
    function unloading() {
        running = false
        poller.stop()
        deadline.stop()
        if (request) request.abort()
        request = null
    }

    function api(method, path, body, complete) {
        if (busy || !running) return
        if (!token) {
            connectionMessage = "Pair this app with the computer before installing."
            return
        }
        busy = true
        var xhr = new XMLHttpRequest()
        request = xhr
        xhr.open(method, serverUrl + path)
        xhr.setRequestHeader("Authorization", "Bearer " + token)
        if (body !== null) xhr.setRequestHeader("Content-Type", "application/json")
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE || !running) return
            deadline.stop()
            request = null
            busy = false
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    var data = JSON.parse(xhr.responseText)
                    online = true
                    connectionMessage = "Connected"
                    complete(data)
                } catch (error) {
                    online = false
                    connectionMessage = "Invalid reply from computer"
                }
            } else {
                online = false
                connectionMessage = xhr.status === 401 ? "Pairing token rejected" : "Computer disconnected · reconnecting"
                if (settings) settingsError = "Could not save. Check the computer connection and try again."
            }
        }
        deadline.restart()
        xhr.send(body === null ? "" : JSON.stringify(body))
    }

    function poll() {
        api("GET", "/v1/display", null, function(data) {
            successfulPolls += 1
            applySnapshot(data)
        })
    }

    function applySnapshot(data) {
        var signature = data.session + ":" + data.sequence + ":" +
            JSON.stringify(data.selected_languages) + ":" + JSON.stringify(data.expected_languages) + ":" +
            JSON.stringify(data.pending_activity) + ":" + JSON.stringify(data.translation_activity) + ":" + data.sync_with_display
        if (signature === lastSignature) return
        lastSignature = signature
        snapshot = data
        catalog = data.languages || []
        speechCatalog = data.speech_languages || []
        expected = data.expected_languages || []
        syncWithDisplay = data.sync_with_display !== false
        var newSelected = data.selected_languages || []
        slotCount = data.slot_count || 6
        if (JSON.stringify(selected) !== JSON.stringify(newSelected) || columns.length === 0) {
            selected = newSelected
            rebuildColumns()
        } else fillRows()
    }

    function rebuildColumns() {
        var nextColumns = showSpoken ? [{code:"_spoken", name:"Spoken", flag:"", direction:"auto"}] : []
        for (var i = 0; i < selected.length; i++) {
            for (var j = 0; j < catalog.length; j++) {
                if (catalog[j].code === selected[i]) nextColumns.push(catalog[j])
            }
        }
        if (readerLayout !== "off" && selected.length) {
            var available = nextColumns.filter(function(item) { return item.code !== "_spoken" })
            if (showSpoken) available.push(nextColumns[0])
            var panels = []
            var count = readerLayout === "four" ? 4 : 2
            for (var panel = 0; panel < count; panel++) {
                var chosen = available[panel % available.length]
                for (var candidate = 0; candidate < available.length; candidate++) {
                    if (available[candidate].code === readerCodes[panel]) chosen = available[candidate]
                }
                var angle = readerAngles[panel] !== undefined ? readerAngles[panel] : defaultReaderAngle(panel)
                panels.push(Object.assign({}, chosen, {panelIndex:panel, panelAngle:angle}))
            }
            nextColumns = panels
        }
        columns = nextColumns
        Qt.callLater(fillRows)
    }

    function defaultReaderAngle(index) {
        return readerLayout === "four" ? (index >= 2 ? 180 : 0) : readerLayout === "stacked" ? (index === 0 ? 180 : 0) : (index === 1 ? 180 : 0)
    }
    function flipReader(index) {
        var next = readerAngles.slice()
        next[index] = (next[index] !== undefined ? next[index] : defaultReaderAngle(index)) === 180 ? 0 : 180
        readerAngles = next
        rebuildColumns()
    }
    function chooseReader(code) {
        var next = readerCodes.slice()
        next[readerTarget] = code
        readerCodes = next
        settings = false
        readerTarget = -1
        rebuildColumns()
    }
    function cycleReaders() {
        var modes = ["off", "opposite", "stacked", "four"]
        readerLayout = modes[(modes.indexOf(readerLayout) + 1) % modes.length]
    }

    function fillRows() {
        for (var column = 0; column < columnRepeater.count; column++) {
            var view = columnRepeater.itemAt(column)
            if (view) view.setRows(snapshot.slots || [])
        }
    }

    function flip(code) {
        var next = Object.assign({}, flipped)
        next[code] = !next[code]
        flipped = next
    }

    function toggleLanguage(code) {
        if (busy || (speechMode && syncWithDisplay)) return
        var current = (speechMode ? expected : selected).slice()
        var position = current.indexOf(code)
        if (position >= 0) {
            if (!speechMode && current.length === 1) return
            current.splice(position, 1)
        } else {
            if (current.length >= 6) return
            current.push(code)
        }
        saveLanguages(current)
    }

    function saveLanguages(codes) {
        settingsError = ""
        api("POST", "/v1/languages", {mode:speechMode ? "speech" : "display", languages:codes},
            function(data) { poll() })
    }

    function setSync(enabled) {
        api("POST", "/v1/languages", {mode:"sync", enabled:enabled}, function(data) { lastSignature = ""; poll() })
    }

    Timer { id: poller; interval: 1000; repeat: true; running: root.running; triggeredOnStart: true; onTriggered: root.poll() }
    Timer {
        id: deadline
        interval: 6000
        onTriggered: {
            if (root.request) root.request.abort()
            root.request = null
            root.busy = false
            root.online = false
            root.connectionMessage = "Computer disconnected · reconnecting"
        }
    }

    Item {
        id: page
        anchors.centerIn: parent
        width: root.pageWidth; height: root.pageHeight
        rotation: root.landscape ? 90 : 0
        Rectangle { anchors.fill: parent; color: "white" }
        Item {
            id: masthead
            width: parent.width; height: root.clean ? 86 : 108
            Text { x: 42; anchors.verticalCenter: parent.verticalCenter; text: "babblet"; font.family: serifFont.name; font.italic: true; font.pixelSize: 37; color: "#50574a" }
            MouseArea { x: 20; width: 230; height: parent.height; onClicked: root.clean = !root.clean }
            ArtButton { anchors.right: parent.right; anchors.rightMargin: 34; anchors.verticalCenter: parent.verticalCenter; width: 76; height: 76; icon: "close"; label: "Close Babblet"; visible: !root.clean; onClicked: { root.unloading(); root.close() } }
        }
        Item {
            id: display
            anchors.top: masthead.bottom; anchors.bottom: dock.top
            anchors.left: parent.left; anchors.right: parent.right
            anchors.leftMargin: 25; anchors.rightMargin: 25
            Repeater {
                id: columnRepeater
                model: root.columns
                delegate: Item {
                    id: column
                    required property var modelData
                    required property int index
                    objectName: "readerPanel-" + index
                    width: root.readerLayout === "stacked" ? display.width : root.readerLayout === "off" ? display.width / Math.max(1, root.columns.length) : (display.width - 32) / 2
                    height: root.readerLayout === "four" || root.readerLayout === "stacked" ? (display.height - 32) / 2 : display.height
                    x: root.readerLayout === "stacked" ? 0 : root.readerLayout === "four" ? Math.floor(index / 2) * (width + 32) : index * (width + (root.readerLayout === "off" ? 0 : 32))
                    y: root.readerLayout === "stacked" ? index * (height + 32) : root.readerLayout === "four" ? (index % 2) * (height + 32) : 0
                    rotation: root.readerLayout === "off" ? 0 : modelData.panelAngle
                    property var language: modelData
                    ListModel { id: rows }
                    Component.onCompleted: {
                        for (var row = 0; row < root.slotCount; row++) rows.append({content:"", source:"", rowId:"", revision:0})
                        Qt.callLater(root.fillRows)
                    }
                    function setRows(items) {
                        while (rows.count < root.slotCount) rows.append({content:"", source:"", rowId:"", revision:0})
                        while (rows.count > root.slotCount) rows.remove(rows.count - 1)
                        for (var row = 0; row < rows.count; row++) {
                            var item = items[row]
                            var pending = root.snapshot.pending_activity || {}
                            var pendingRow = pending.active ? (pending.display_index - 1) % root.slotCount : -1
                            var placeholder = row === pendingRow && (!item || item.utterance_id !== pending.utterance_id)
                            var translated = item && item.translations ? item.translations[language.code] : null
                            var content = placeholder || !item ? "" : language.code === "_spoken" ? item.source_text : translated && translated.text ? translated.text : ""
                            var source = !placeholder && item && language.code === "_spoken" ? item.source_language : ""
                            var id = item ? item.utterance_id : ""
                            var previous = rows.get(row)
                            if (previous.content !== content || previous.source !== source || previous.rowId !== id) {
                                rows.set(row, {content:content, source:source, rowId:id, revision:item ? item.revision : 0})
                                root.changedCells += 1
                            }
                        }
                    }
                    Item {
                        id: heading
                        objectName: "columnHeader-" + column.language.code
                        width: parent.width; height: 82
                        rotation: root.readerLayout === "off" && root.flipped[column.language.code] ? 180 : 0
                        Text { anchors.centerIn: parent; text: column.language.code === "_spoken" ? "spoken" : ""; font.family: serifFont.name; font.italic: true; font.pixelSize: 24; color: "#777d70" }
                        Image { anchors.centerIn: parent; width: 50; height: 35; fillMode: Image.PreserveAspectFit; source: column.language.flag ? "../flags/" + column.language.flag + ".svg" : "" }
                        Image { anchors.right: parent.right; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter; width: 28; height: 28; source: "../art/flip.svg" }
                        MouseArea { anchors.fill: parent; onClicked: { if (root.readerLayout === "off") root.flip(column.language.code); else root.flipReader(column.index) } }
                        ArtButton { visible: root.readerLayout !== "off"; x: 4; width: 68; height: 68; icon: "languages"; label: "Reader language"; onClicked: { root.readerTarget = column.index; root.speechMode = false; root.searchText = ""; root.settings = true } }
                    }
                    Repeater {
                        model: rows
                        delegate: Item {
                            required property int index
                            required property string content
                            required property string source
                            required property string rowId
                            required property int revision
                            objectName: "tabletRow-" + column.index + "-" + index
                            width: column.width - 54
                            height: (column.height - heading.height) / root.slotCount
                            x: 27; y: heading.height + index * height
                            rotation: root.readerLayout === "off" && root.flipped[column.language.code] ? 180 : 0
                            clip: true
                            opacity: index === root.nextReplaceRow ? 0.45 : 1
                            Rectangle {
                                x: 0; y: 19; width: 8; height: 8; radius: 4
                                color: "#526047"; visible: index === root.latestRow
                            }
                            Text { x: 0; y: 8; text: source; font.family: latinFont.name; font.pixelSize: 14; color: "#8b9084" }
                            Text {
                                objectName: "tabletCell"
                                x: 0; y: 34; width: parent.width; height: parent.height - 50
                                text: content; textFormat: Text.PlainText; wrapMode: Text.Wrap
                                font.family: root.fontFor(column.language.code === "_spoken" ? source : column.language.code)
                                font.pixelSize: root.columns.length > 4 ? 27 : 32
                                minimumPixelSize: 18; fontSizeMode: Text.Fit; elide: Text.ElideRight
                                color: "#272b24"; renderType: Text.NativeRendering
                                horizontalAlignment: column.language.direction === "rtl" || ["he", "ar", "fa", "ur"].indexOf(source) >= 0 ? Text.AlignRight : Text.AlignLeft
                                verticalAlignment: Text.AlignTop
                            }
                        }
                    }
                }
            }
            Rectangle {
                visible: root.readerLayout === "stacked" || root.readerLayout === "four"
                x: 38; y: (parent.height - height) / 2
                width: parent.width - 76; height: 2; color: "#89917f"
            }
            Rectangle {
                visible: root.readerLayout === "opposite" || root.readerLayout === "four"
                x: (parent.width - width) / 2; y: 28
                width: 2; height: parent.height - 56; color: "#89917f"
            }
            Rectangle {
                visible: root.workVisible && root.readerLayout !== "off"
                width: 90; height: 90; radius: 45; color: "white"
                anchors.centerIn: parent
            }
            Image {
                id: work
                objectName: "workCue"
                visible: root.workVisible
                width: 84; height: 84; x: (display.width - width) / 2
                y: root.readerLayout === "off" ? 82 + root.workRow * ((display.height - 82) / root.slotCount) + 24 : (display.height - height) / 2
                source: "../art/work-" + root.workLevel + ".svg"
            }
            Text { anchors.centerIn: parent; visible: !root.online && root.columns.length === 0; text: root.connectionMessage; font.family: serifFont.name; font.pixelSize: 30; color: "#787e71" }
        }
        Item {
            id: dock
            width: parent.width; height: 120; anchors.bottom: parent.bottom
            ArtButton { x: 28; anchors.verticalCenter: parent.verticalCenter; icon: "landscape"; label: "Switch portrait or landscape"; selected: root.landscape; onClicked: root.landscape = !root.landscape }
            ArtButton { objectName: "spokenToggle"; x: 146; anchors.verticalCenter: parent.verticalCenter; icon: "spoken"; label: "Show original speech"; selected: root.showSpoken; onClicked: root.showSpoken = !root.showSpoken }
            TapButton { x: 270; anchors.verticalCenter: parent.verticalCenter; text: root.readerLayout === "off" ? "Readers" : root.readerLayout === "opposite" ? "Facing columns" : root.readerLayout === "stacked" ? "Facing stacked" : "Four panels"; selected: root.readerLayout !== "off"; onClicked: root.cycleReaders() }
            Text { anchors.centerIn: parent; text: root.online ? "" : root.connectionMessage; font.family: serifFont.name; font.italic: true; font.pixelSize: 19; color: "#7b8273" }
        }
        Rectangle {
            id: languageSheet
            anchors.fill: parent; color: "white"; visible: root.settings
            rotation: root.readerTarget >= 0 && root.columns[root.readerTarget] ? root.columns[root.readerTarget].panelAngle : 0
            Text { x: 50; y: 32; text: root.readerTarget >= 0 ? "Reader language" : "Languages"; font.family: serifFont.name; font.italic: true; font.pixelSize: 50; color: "#30372a" }
            ArtButton { anchors.right: parent.right; anchors.rightMargin: 36; y: 15; width: 86; height: 86; icon: "close"; label: "Close language picker"; onClicked: { root.settings = false; root.readerTarget = -1 } }
            Row {
                x: 50; y: 125; spacing: 18; visible: root.readerTarget < 0
                TapButton { text: "Read"; selected: !root.speechMode; onClicked: root.speechMode = false }
                TapButton { text: "Hear"; selected: root.speechMode; onClicked: root.speechMode = true }
            }
            Row {
                x: 50; y: 210; spacing: 18; visible: root.readerTarget < 0
                ArtButton { icon: "link"; width: 72; height: 72; label: "Link spoken and display languages"; selected: root.syncWithDisplay; onClicked: { if (!root.busy) root.setSync(!root.syncWithDisplay) } }
                Text { anchors.verticalCenter: parent.verticalCenter; text: root.syncWithDisplay ? "Read and hear the same languages" : "Choose spoken languages separately"; font.family: latinFont.name; font.pixelSize: 23; color: "#5f6856" }
            }
            TapButton { x: 50; y: 145; visible: root.readerTarget >= 0 && root.showSpoken; text: "Original speech"; onClicked: root.chooseReader("_spoken") }
            Text { x: 50; y: 280; text: root.readerTarget >= 0 ? "Choose from displayed languages. Add more with the main language button." : root.settingsError || (root.speechMode && root.syncWithDisplay ? "Linked to Read. Unlink to choose separately." : "Tap a flag. Your choice is saved."); font.family: latinFont.name; font.pixelSize: 21; color: "#7b8372" }
            Rectangle {
                x: 480; y: 125; width: Math.min(620, page.width - 530); height: 68; color: "#f3f4ef"; radius: 10
                TextInput { id: search; anchors.fill: parent; anchors.margins: 17; font.family: latinFont.name; font.pixelSize: 24; color: "#30372a"; text: root.searchText; onTextChanged: root.searchText = text; clip: true }
                Text { anchors.fill: parent; anchors.margins: 17; text: "Find a language"; visible: !search.text && !search.activeFocus; font.family: serifFont.name; font.italic: true; font.pixelSize: 24; color: "#89917e" }
            }
            Item {
                objectName: "languageGridViewport"
                x: 35; y: 330; width: parent.width - 70; height: parent.height - 450
                clip: true
                Grid {
                    id: languageGrid
                    objectName: "languageGrid"
                    columns: page.width > page.height ? 8 : 5; spacing: 12
                    readonly property int rowCount: Math.max(1, Math.ceil(root.languageOptions.length / columns))
                    readonly property real tileHeight: Math.min(160, (parent.height - (rowCount - 1) * spacing) / rowCount)
                    Repeater {
                        model: root.languageOptions
                        delegate: Item {
                            required property var modelData
                            width: (languageGrid.parent.width - (languageGrid.columns - 1) * languageGrid.spacing) / languageGrid.columns
                            height: languageGrid.tileHeight
                            property bool picked: root.readerTarget >= 0 ? root.columns[root.readerTarget].code === modelData.code : (root.speechMode ? root.expected : root.selected).indexOf(modelData.code) >= 0
                            Image { anchors.horizontalCenter: parent.horizontalCenter; y: 0; width: 90; height: 90; source: "../art/halo.svg"; visible: parent.picked }
                            Image { anchors.horizontalCenter: parent.horizontalCenter; y: 24; width: 60; height: 42; fillMode: Image.PreserveAspectFit; source: "../flags/" + modelData.flag + ".svg" }
                            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 95; width: parent.width - 8; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; text: modelData.name; font.family: serifFont.name; font.pixelSize: 20; color: "#30372a" }
                            Text { anchors.horizontalCenter: parent.horizontalCenter; y: 125; width: parent.width - 8; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; text: root.nativeCaption(modelData); font.family: root.fontFor(modelData.code); font.pixelSize: 18; color: "#878e7c" }
                            MouseArea { anchors.fill: parent; enabled: !root.busy && !(root.speechMode && root.syncWithDisplay); onClicked: { if (root.readerTarget >= 0) root.chooseReader(modelData.code); else root.toggleLanguage(modelData.code) } }
                        }
                    }
                }
            }
        }
        ArtButton {
            id: languagePicker
            objectName: "languagePickerButton"
            anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 22
            width: 106; height: 106; icon: "languages"; label: "Choose languages"
            selected: root.settings; onClicked: { root.readerTarget = -1; root.settings = !root.settings }
        }
    }
}
