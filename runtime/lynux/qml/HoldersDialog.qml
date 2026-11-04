import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kirigami.delegates as Delegates

Kirigami.Dialog {
    id: dialog

    property var shell
    property var groups: []
    property bool force: false
    property var selected: ({})

    function show(list, forceQuit) {
        const choice = {}
        for (const group of list)
            choice[group.id] = true
        groups = list
        selected = choice
        force = forceQuit
        open()
    }

    function chosen() {
        return groups.filter(group => selected[group.id]).map(group => group.id)
    }

    function detail(group) {
        if (group.kind === "session")
            return app.s.holders_session.arg(group.processes.length)
        return app.s.holders_process.arg(group.processes[0].pid).arg(group.processes[0].user)
    }

    title: app.s.holders_title
    preferredWidth: Kirigami.Units.gridUnit * 30
    padding: Kirigami.Units.largeSpacing
    standardButtons: Kirigami.Dialog.NoButton
    customFooterActions: [
        Kirigami.Action {
            text: dialog.force ? app.s.holders_force : app.s.holders_end
            icon.name: "process-stop"
            enabled: dialog.chosen().length > 0 && !app.busy
            onTriggered: {
                app.lock(dialog.chosen(), dialog.force)
                dialog.close()
            }
        },
        Kirigami.Action {
            text: app.s.cancel
            icon.name: "dialog-cancel"
            onTriggered: dialog.close()
        }
    ]

    ColumnLayout {
        spacing: Kirigami.Units.smallSpacing

        QQC2.Label {
            Layout.fillWidth: true

            Layout.maximumWidth: Kirigami.Units.gridUnit * 28
            Layout.bottomMargin: Kirigami.Units.smallSpacing
            text: dialog.force ? app.s.holders_still : app.s.holders_desc
            wrapMode: Text.Wrap
        }

        Repeater {
            model: dialog.groups

            delegate: Delegates.CheckSubtitleDelegate {
                id: item

                required property var modelData

                Layout.fillWidth: true
                text: modelData.title
                subtitle: dialog.detail(modelData)
                icon.name: modelData.kind === "session" ? "utilities-terminal" : "system-run"
                checked: dialog.selected[modelData.id] === true
                onToggled: {
                    const choice = Object.assign({}, dialog.selected)
                    choice[modelData.id] = checked
                    dialog.selected = choice
                }

                QQC2.ToolTip.visible: hovered && modelData.processes[0].command !== ""
                QQC2.ToolTip.text: modelData.processes.map(info => info.command || info.name).join("\n")
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            }
        }
    }
}
