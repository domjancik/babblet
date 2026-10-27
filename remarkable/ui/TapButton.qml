import QtQuick 2.15

Rectangle {
    id: button
    property string text: ""
    property bool selected: false
    signal clicked()
    implicitWidth: Math.max(120, label.implicitWidth + 48)
    implicitHeight: 64
    color: selected ? "#ecefe5" : "white"
    radius: 20
    opacity: enabled ? 1 : 0.4
    Text {
        id: label
        anchors.centerIn: parent
        text: button.text
        color: "black"
        font.pixelSize: 22
        font.family: "Noto Serif"
        font.italic: true
        renderType: Text.NativeRendering
    }
    MouseArea { anchors.fill: parent; onClicked: button.clicked() }
}
