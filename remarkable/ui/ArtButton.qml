import QtQuick 2.15

Item {
    // The tablet's stripped Qt build has no Accessible attached object.
    id: button
    property string icon: ""
    property string label: ""
    property bool selected: false
    signal clicked()
    width: 100; height: 100
    Image { anchors.fill: parent; visible: button.selected; source: "../art/halo.svg" }
    Image { anchors.centerIn: parent; width: parent.width * 0.72; height: width; source: "../art/" + button.icon + ".svg" }
    MouseArea { anchors.fill: parent; onClicked: button.clicked() }
}
